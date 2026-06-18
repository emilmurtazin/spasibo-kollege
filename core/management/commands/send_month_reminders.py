"""
Напоминание сотрудникам об остатке монеток в конце месяца.

Запускать через cron за 3 дня до конца каждого месяца:
    0 10 28 * * cd /path/to/project && python manage.py send_month_reminders
"""

import calendar
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import User
from core.telegram_bot import notify_month_reminder


class Command(BaseCommand):
    help = 'Отправляет Telegram-напоминания сотрудникам об остатке монеток.'

    def add_arguments(self, parser):
        parser.add_argument('--days-left', type=int, default=3,
            help='Сколько дней до конца месяца (по умолчанию 3)')

    def handle(self, *args, **options):
        today     = timezone.now().date()
        days_left = options['days_left']

        # Считаем сколько дней осталось до конца текущего месяца
        last_day     = calendar.monthrange(today.year, today.month)[1]
        actual_left  = last_day - today.day

        users = User.objects.filter(
            is_active=True,
            telegram_chat_id__isnull=False,
            balance__gt=0,
        )

        sent = 0
        for user in users:
            try:
                notify_month_reminder(user, days_left=actual_left)
                sent += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Ошибка для {user}: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'Напоминания отправлены {sent} сотрудникам ({today:%d.%m.%Y}). '
            f'До конца месяца: {actual_left} дн.'
        ))
