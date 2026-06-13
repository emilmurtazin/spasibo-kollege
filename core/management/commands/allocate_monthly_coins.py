"""
Ежемесячное начисление монет всем сотрудникам.

Запускать 1-го числа каждого месяца через cron, например:
    0 6 1 * * cd /path/to/project && /path/to/venv/bin/python manage.py allocate_monthly_coins
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.utils import timezone

from core.models import User, Transaction


class Command(BaseCommand):
    help = 'Начисляет всем активным сотрудникам ежемесячную порцию монет (по умолчанию 30).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Начислить монеты, даже если уже начислялись в этом месяце.',
        )

    def handle(self, *args, **options):
        today = timezone.now().date()
        amount = settings.MONTHLY_COIN_ALLOCATION
        force = options['force']

        users = User.objects.filter(is_active=True)
        updated = 0

        for user in users:
            already_done = (
                user.last_monthly_allocation
                and user.last_monthly_allocation.year == today.year
                and user.last_monthly_allocation.month == today.month
            )
            if already_done and not force:
                continue

            with db_transaction.atomic():
                user.balance += amount
                user.last_monthly_allocation = today
                user.save(update_fields=['balance', 'last_monthly_allocation'])

                Transaction.objects.create(
                    from_user=None,
                    to_user=user,
                    amount=amount,
                    comment='Ежемесячное начисление монет',
                    type='admin',
                    month=today.month,
                    year=today.year,
                )
            updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Начислено по {amount} монет {updated} сотрудникам ({today:%d.%m.%Y}).'
        ))
