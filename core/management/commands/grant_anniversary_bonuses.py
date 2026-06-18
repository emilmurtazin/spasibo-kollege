"""
Бонусы за стаж работы.

Запускать ежедневно через cron, например:
    0 6 * * * cd /path/to/project && /path/to/venv/bin/python manage.py grant_anniversary_bonuses

Для каждого сотрудника проверяется, не наступила ли сегодня (или в течение
последних суток) дата очередной "годовщины" (3, 6, 12, 24, 36 месяцев с
момента hire_date). Если да и бонус ещё не выдавался — начисляются монеты.
"""

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.utils import timezone

from core.models import User, Transaction


class Command(BaseCommand):
    help = 'Начисляет бонусные монеты сотрудникам за стаж работы (3, 6, 12, 24, 36 месяцев).'

    def handle(self, *args, **options):
        today = timezone.now().date()
        bonuses = settings.ANNIVERSARY_BONUSES  # {months: amount}
        granted = 0

        users = User.objects.filter(is_active=True, hire_date__isnull=False)

        for user in users:
            for months, amount in bonuses.items():
                anniversary_date = user.hire_date + relativedelta(months=months)

                if anniversary_date != today:
                    continue

                # не начислять повторно, если бонус за эту дату уже выдан
                if user.last_bonus_date == today:
                    continue

                with db_transaction.atomic():
                    user.balance += amount
                    user.last_bonus_date = today
                    user.save(update_fields=['balance', 'last_bonus_date'])

                    Transaction.objects.create(
                        from_user=None,
                        to_user=user,
                        amount=amount,
                        comment=f'Бонус за стаж: {months} мес. в компании',
                        type='bonus',
                        month=today.month,
                        year=today.year,
                    )
                granted += 1

        self.stdout.write(self.style.SUCCESS(
            f'Бонусы за стаж начислены {granted} сотрудникам ({today:%d.%m.%Y}).'
        ))
