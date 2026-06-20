"""
Бонусы за стаж работы.

Запускать ежедневно через cron, например:
    0 6 * * * cd /path/to/project && /path/to/venv/bin/python manage.py grant_anniversary_bonuses

Логика:
  - Бонусы за стаж настраиваются администратором каждой компании
    (модель SeniorityBonus: "N дней стажа -> M монет").
  - Стаж считается как точное количество КАЛЕНДАРНЫХ ДНЕЙ
    с даты hire_date до сегодня (не месяцев/округлений).
  - Команда "добирает" все бонусы, для которых стаж уже наступил,
    но грант ещё не выдан (SeniorityBonusGrant) — поэтому пропуск
    запуска cron на день-два не приводит к потере начисления.
  - Каждый бонус выдаётся ровно один раз на пользователя
    (защита через unique_together в SeniorityBonusGrant).
"""

from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.utils import timezone

from core.models import User, Transaction, SeniorityBonus, SeniorityBonusGrant


class Command(BaseCommand):
    help = 'Начисляет бонусные монеты сотрудникам за стаж работы по настройкам компании.'

    def handle(self, *args, **options):
        today   = timezone.now().date()
        granted = 0

        users = User.objects.filter(
            is_active=True, hire_date__isnull=False, company__isnull=False
        ).select_related('company')

        for user in users:
            days_employed = (today - user.hire_date).days
            if days_employed < 0:
                continue  # дата приёма в будущем — пропускаем

            # Все активные бонусы компании, для которых стаж уже наступил
            eligible_bonuses = SeniorityBonus.objects.filter(
                company=user.company,
                is_active=True,
                days_required__lte=days_employed,
            )

            for bonus in eligible_bonuses:
                # Пропускаем, если этот конкретный бонус уже выдан этому юзеру
                already_granted = SeniorityBonusGrant.objects.filter(
                    user=user, bonus=bonus
                ).exists()
                if already_granted:
                    continue

                with db_transaction.atomic():
                    user.balance += bonus.coins_amount
                    user.last_bonus_date = today
                    user.save(update_fields=['balance', 'last_bonus_date'])

                    Transaction.objects.create(
                        from_user=None,
                        to_user=user,
                        amount=bonus.coins_amount,
                        comment=f'Бонус за стаж: {bonus.days_required} дн. в компании',
                        type='bonus',
                        month=today.month,
                        year=today.year,
                    )

                    SeniorityBonusGrant.objects.create(user=user, bonus=bonus)

                granted += 1

        self.stdout.write(self.style.SUCCESS(
            f'Бонусы за стаж начислены {granted} раз(а) ({today:%d.%m.%Y}).'
        ))
