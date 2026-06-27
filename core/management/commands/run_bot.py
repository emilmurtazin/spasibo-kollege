"""
Запуск Telegram-бота в режиме polling (без webhook).

Используется когда webhook недоступен из-за сетевых ограничений.
Бот сам опрашивает Telegram API каждые 2 секунды через исходящий прокси.

Запуск:
    python manage.py run_bot

На Timeweb App Platform добавьте в Procfile:
    worker: python manage.py run_bot
"""

import time
import logging

import requests
from django.core.management.base import BaseCommand
from django.conf import settings

from core.telegram_bot import handle_update

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Запускает Telegram-бота в режиме long polling'

    def handle(self, *args, **options):
        token     = settings.TELEGRAM_BOT_TOKEN
        proxy_url = getattr(settings, 'TELEGRAM_PROXY_URL', '')
        proxies   = {'https': proxy_url, 'http': proxy_url} if proxy_url else None

        if not token:
            self.stderr.write('TELEGRAM_BOT_TOKEN не задан')
            return

        self.stdout.write('Бот запущен в режиме polling...')

        # Сначала удаляем webhook если был установлен
        try:
            requests.post(
                f'https://api.telegram.org/bot{token}/deleteWebhook',
                json={'drop_pending_updates': True},
                proxies=proxies, timeout=10
            )
            self.stdout.write('Webhook удалён')
        except Exception as e:
            self.stdout.write(f'Не удалось удалить webhook: {e}')

        offset = 0

        while True:
            try:
                r = requests.post(
                    f'https://api.telegram.org/bot{token}/getUpdates',
                    json={
                        'offset': offset,
                        'timeout': 30,
                        'allowed_updates': ['message', 'callback_query'],
                    },
                    proxies=proxies,
                    timeout=35,
                )
                data = r.json()

                if not data.get('ok'):
                    self.stderr.write(f'Ошибка getUpdates: {data}')
                    time.sleep(5)
                    continue

                updates = data.get('result', [])
                for update in updates:
                    try:
                        handle_update(update)
                    except Exception as e:
                        logger.error(f'Ошибка обработки update {update.get("update_id")}: {e}')
                    offset = update['update_id'] + 1

            except requests.exceptions.Timeout:
                # Таймаут long polling — это нормально, просто продолжаем
                continue
            except Exception as e:
                logger.error(f'Ошибка polling: {e}')
                time.sleep(5)
