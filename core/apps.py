from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Спасибо, коллега'

    def ready(self):
        import core.signals  # noqa: F401
        self._start_telegram_polling()

    def _start_telegram_polling(self):
        """Запускает Telegram-бота в фоновом потоке при старте Django."""
        import os

        # Не запускаем во время manage.py команд (migrate, shell, etc.)
        import sys
        if len(sys.argv) > 1 and sys.argv[1] in (
            'migrate', 'makemigrations', 'shell', 'collectstatic',
            'createsuperuser', 'dbshell', 'showmigrations', 'run_bot',
        ):
            return

        from django.conf import settings
        if not getattr(settings, 'TELEGRAM_BOT_TOKEN', ''):
            return  # токен не задан

        import threading
        import logging
        logger = logging.getLogger(__name__)

        def polling_loop():
            import time
            import requests
            from core.telegram_bot import handle_update

            token     = settings.TELEGRAM_BOT_TOKEN
            proxy_url = getattr(settings, 'TELEGRAM_PROXY_URL', '')
            proxies   = {'https': proxy_url, 'http': proxy_url} if proxy_url else None

            # Удаляем webhook чтобы не было конфликта
            try:
                requests.post(
                    f'https://api.telegram.org/bot{token}/deleteWebhook',
                    json={'drop_pending_updates': True},
                    proxies=proxies, timeout=10
                )
                logger.info('Telegram webhook deleted, starting polling')
            except Exception as e:
                logger.warning(f'Could not delete webhook: {e}')

            offset = 0

            while True:
                try:
                    r = requests.post(
                        f'https://api.telegram.org/bot{token}/getUpdates',
                        json={
                            'offset': offset,
                            'timeout': 25,
                            'allowed_updates': ['message', 'callback_query'],
                        },
                        proxies=proxies,
                        timeout=30,
                    )
                    data = r.json()

                    if not data.get('ok'):
                        logger.error(f'getUpdates error: {data}')
                        time.sleep(5)
                        continue

                    for update in data.get('result', []):
                        try:
                            handle_update(update)
                        except Exception as e:
                            logger.error(f'handle_update error: {e}')
                        offset = update['update_id'] + 1

                except requests.exceptions.Timeout:
                    continue  # long polling timeout — нормально
                except Exception as e:
                    logger.error(f'Polling error: {e}')
                    time.sleep(5)

        t = threading.Thread(target=polling_loop, name='telegram-polling', daemon=True)
        t.start()
        logger.info('Telegram polling thread started')
