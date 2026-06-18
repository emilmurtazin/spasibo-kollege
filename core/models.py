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


class Transaction(models.Model):
    """Движение монет: подарок коллеге, покупка награды или начисление администратором."""

    TYPE_CHOICES = [
        ('give', 'Подарок коллеге'),
        ('reward', 'Покупка награды'),
        ('admin', 'Начисление администратором'),
        ('bonus', 'Бонус за стаж'),
    ]

    from_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='sent',
        verbose_name='От кого', null=True, blank=True,
    )
    to_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='received',
        verbose_name='Кому', null=True, blank=True,
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
