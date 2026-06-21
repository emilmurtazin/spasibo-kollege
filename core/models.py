from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings


class Company(models.Model):
    """Компания-клиент платформы."""

    PLAN_CHOICES = [
        ('start', 'Старт'),
        ('team', 'Команда'),
        ('corp', 'Корпорация'),
    ]

    name = models.CharField('Название компании', max_length=255)
    inn = models.CharField(
        'ИНН', max_length=12, blank=True,
        help_text='10 цифр для юрлица, 12 — для ИП. Нужен, чтобы отличать компании с одинаковым названием.',
    )
    subscription_plan = models.CharField(
        'Тарифный план', max_length=20, choices=PLAN_CHOICES, default='start'
    )
    employee_limit = models.IntegerField('Лимит сотрудников', default=25)
    created_at = models.DateTimeField('Дата регистрации', auto_now_add=True)

    class Meta:
        verbose_name = 'Компания'
        verbose_name_plural = 'Компании'

    def __str__(self):
        return self.name

    def employees_count(self):
        return self.users.count()


class Reward(models.Model):
    """Награда, которую сотрудник может получить за монеты."""

    CATEGORY_CHOICES = [
        ('material', 'Материальная'),
        ('event', 'Событие'),
        ('development', 'Развитие'),
        ('wellbeing', 'Well-being'),
        ('intangible', 'Нематериальная'),
    ]

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='rewards', verbose_name='Компания'
    )
    name = models.CharField('Название', max_length=255)
    description = models.TextField('Описание', blank=True)
    price = models.IntegerField('Стоимость (монет)')
    category = models.CharField('Категория', max_length=20, choices=CATEGORY_CHOICES, default='material')
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        verbose_name = 'Награда'
        verbose_name_plural = 'Награды'
        ordering = ['price']

    def __str__(self):
        return f'{self.name} ({self.price} монет)'


class User(AbstractUser):
    """Пользователь платформы — сотрудник компании."""

    ROLE_CHOICES = [
        ('employee', 'Сотрудник'),
        ('admin', 'Администратор / HR'),
    ]

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='users',
        verbose_name='Компания', null=True, blank=True,
    )
    balance = models.IntegerField('Баланс монет', default=0)
    role = models.CharField('Роль', max_length=20, choices=ROLE_CHOICES, default='employee')
    current_goal = models.TextField('Текущая цель', blank=True)
    target_reward = models.ForeignKey(
        Reward, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='target_of', verbose_name='Награда-цель',
    )
    telegram_chat_id = models.BigIntegerField('Telegram chat ID', null=True, blank=True)
    department = models.CharField('Отдел', max_length=255, blank=True)
    hire_date = models.DateField('Дата приёма на работу', null=True, blank=True)
    last_monthly_allocation = models.DateField('Дата последнего начисления', null=True, blank=True)
    last_bonus_date = models.DateField('Дата последнего бонуса за стаж', null=True, blank=True)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def is_company_admin(self):
        return self.role == 'admin'

    def coins_given_to(self, other_user, year, month):
        """Сколько монет уже отправлено конкретному коллеге в указанном месяце."""
        return self.sent.filter(
            to_user=other_user, type='give', year=year, month=month
        ).aggregate(total=models.Sum('amount'))['total'] or 0

    def purchasable_balance(self):
        """
        Сколько монеток доступно для покупки наград / зачёта цели.

        В зачёт идут только монетки от коллег (type=give) и бонусы за стаж
        (type=bonus). Ежемесячные системные начисления (type=admin) сюда
        не входят — их можно только дарить коллегам, не тратить на награды.
        """
        earned = self.received.filter(
            type__in=['give', 'bonus']
        ).aggregate(total=models.Sum('amount'))['total'] or 0

        spent = self.sent.filter(
            type='reward'
        ).aggregate(total=models.Sum('amount'))['total'] or 0

        return max(0, earned - spent)


class Transaction(models.Model):
    """Движение монет: подарок коллеге, покупка награды или начисление администратором."""

    TYPE_CHOICES = [
        ('give', 'Подарок коллеге'),
        ('reward', 'Покупка награды'),
        ('admin', 'Начисление администратором'),
        ('bonus', 'Бонус за стаж'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Ожидает исполнения'),
        ('fulfilled', 'Исполнено'),
    ]

    from_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='sent',
        verbose_name='От кого', null=True, blank=True,
    )
    to_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='received',
        verbose_name='Кому', null=True, blank=True,
    )
    reward = models.ForeignKey(
        'Reward', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='purchases', verbose_name='Награда',
        help_text='Заполняется только для транзакций типа "Покупка награды"',
    )
    status = models.CharField(
        'Статус исполнения', max_length=20, choices=STATUS_CHOICES,
        default='pending',
        help_text='Актуально только для покупок наград (type=reward)',
    )
    fulfilled_at = models.DateTimeField('Дата исполнения', null=True, blank=True)
    fulfilled_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fulfilled_rewards', verbose_name='Кто исполнил',
    )
    amount = models.IntegerField('Количество монет')
    comment = models.TextField('Комментарий', blank=True)
    type = models.CharField('Тип транзакции', max_length=20, choices=TYPE_CHOICES, default='give')
    month = models.IntegerField('Месяц')
    year = models.IntegerField('Год')
    date = models.DateTimeField('Дата и время', auto_now_add=True)

    class Meta:
        verbose_name = 'Транзакция'
        verbose_name_plural = 'Транзакции'
        ordering = ['-date']

    def __str__(self):
        return f'{self.get_type_display()}: {self.from_user} -> {self.to_user} ({self.amount})'


class ENPSSurvey(models.Model):
    """Опрос лояльности сотрудников (eNPS)."""

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='enps_surveys', verbose_name='Компания'
    )
    started_at = models.DateTimeField('Дата запуска', auto_now_add=True)
    responses = models.JSONField('Ответы', default=list, blank=True)
    average_score = models.FloatField('Средний балл', null=True, blank=True)

    class Meta:
        verbose_name = 'Опрос eNPS'
        verbose_name_plural = 'Опросы eNPS'
        ordering = ['-started_at']

    def __str__(self):
        return f'eNPS {self.company} от {self.started_at:%d.%m.%Y}'

    def recalculate_average(self):
        """Пересчитать средний балл по сохранённым ответам.

        Каждый элемент responses — словарь вида {"score": int, ...}.
        """
        scores = [r.get('score') for r in self.responses if isinstance(r, dict) and r.get('score') is not None]
        self.average_score = sum(scores) / len(scores) if scores else None
        return self.average_score


class ENPSParticipation(models.Model):
    """
    Факт участия сотрудника в опросе eNPS — нужен ТОЛЬКО для того,
    чтобы не дать ответить дважды. Сам ответ (балл, комментарий)
    в этой модели не хранится и никак не связан с конкретным сотрудником —
    он лежит анонимно в ENPSSurvey.responses.
    """

    survey      = models.ForeignKey(ENPSSurvey, on_delete=models.CASCADE, related_name='participations')
    user        = models.ForeignKey('User', on_delete=models.CASCADE, related_name='enps_participations')
    answered_at = models.DateTimeField('Дата ответа', auto_now_add=True)

    class Meta:
        verbose_name = 'Участие в опросе eNPS'
        verbose_name_plural = 'Участия в опросах eNPS'
        unique_together = [['survey', 'user']]

    def __str__(self):
        return f'{self.user} ответил(а) на опрос {self.survey_id}'


class TelegramLinkToken(models.Model):
    """Одноразовый токен для привязки Telegram-аккаунта к профилю."""

    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='telegram_link_token')
    token      = models.CharField('Токен', max_length=64, unique=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    used       = models.BooleanField('Использован', default=False)

    class Meta:
        verbose_name = 'Токен привязки Telegram'
        verbose_name_plural = 'Токены привязки Telegram'

    def __str__(self):
        return f'TelegramLink {self.user} ({self.token[:8]}…)'

    @classmethod
    def generate_for(cls, user):
        import secrets
        cls.objects.filter(user=user).delete()
        return cls.objects.create(user=user, token=secrets.token_urlsafe(32))


class CompanyInvite(models.Model):
    """Пригласительная ссылка для самостоятельной регистрации сотрудников."""

    company    = models.ForeignKey(Company, on_delete=models.CASCADE,
                                   related_name='invites', verbose_name='Компания')
    token      = models.CharField('Токен', max_length=32, unique=True)
    created_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True,
                                   related_name='created_invites', verbose_name='Создал')
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    expires_at = models.DateTimeField('Действует до', null=True, blank=True)
    is_active  = models.BooleanField('Активна', default=True)
    uses_count = models.IntegerField('Использований', default=0)

    class Meta:
        verbose_name = 'Приглашение'
        verbose_name_plural = 'Приглашения'
        ordering = ['-created_at']

    def __str__(self):
        return f'Invite {self.company} ({self.token[:8]}…)'

    @property
    def is_valid(self):
        from django.utils import timezone
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True

    @classmethod
    def generate(cls, company, created_by, days_valid=30):
        import secrets
        from django.utils import timezone
        from datetime import timedelta
        return cls.objects.create(
            company=company,
            created_by=created_by,
            token=secrets.token_urlsafe(20),
            expires_at=timezone.now() + timedelta(days=days_valid),
        )


class SupportRequest(models.Model):
    """Обращение пользователя в службу поддержки."""

    STATUS_CHOICES = [
        ('new', 'Новое'),
        ('answered', 'Отвечено'),
    ]

    user      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_requests')
    company   = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='support_requests', null=True, blank=True)
    subject   = models.CharField('Тема', max_length=255)
    message   = models.TextField('Сообщение')
    status    = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='new')
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Обращение в поддержку'
        verbose_name_plural = 'Обращения в поддержку'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} — {self.subject} ({self.created_at:%d.%m.%Y})'


class SeniorityBonus(models.Model):
    """
    Настраиваемый администратором бонус за стаж работы.

    Например: 90 дней работы -> 15 монет. Компания может задать свои
    правила вместо жёстко прописанных в коде.
    """

    company       = models.ForeignKey(Company, on_delete=models.CASCADE,
                                      related_name='seniority_bonuses', verbose_name='Компания')
    days_required = models.IntegerField('Дней стажа', help_text='Количество календарных дней с даты приёма')
    coins_amount  = models.IntegerField('Монет к начислению')
    is_active     = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Бонус за стаж'
        verbose_name_plural = 'Бонусы за стаж'
        ordering = ['days_required']
        unique_together = [['company', 'days_required']]

    def __str__(self):
        return f'{self.company}: {self.days_required} дн. → {self.coins_amount} монет'


class SeniorityBonusGrant(models.Model):
    """
    Факт начисления конкретного бонуса за стаж конкретному сотруднику.

    Нужен, чтобы:
    - не начислить один и тот же бонус дважды
    - не потерять начисление, если cron пропустил точный день
      (команда добирает все бонусы, для которых стаж уже наступил,
      но грант ещё не создан — а не только "ровно сегодня")
    """

    user      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seniority_grants')
    bonus     = models.ForeignKey(SeniorityBonus, on_delete=models.CASCADE, related_name='grants')
    granted_at = models.DateTimeField('Начислено', auto_now_add=True)

    class Meta:
        verbose_name = 'Начисление бонуса за стаж'
        verbose_name_plural = 'Начисления бонусов за стаж'
        unique_together = [['user', 'bonus']]

    def __str__(self):
        return f'{self.user} — {self.bonus}'
