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
        import sys

        # Не запускаем во время manage.py команд
        if len(sys.argv) > 1 and sys.argv[1] in (
            'migrate', 'makemigrations', 'shell', 'collectstatic',
            'createsuperuser', 'dbshell', 'showmigrations', 'run_bot',
            'grant_anniversary_bonuses', 'allocate_monthly_coins',
            'send_month_reminders',
        ):
            return

        from django.conf import settings
        if not getattr(settings, 'TELEGRAM_BOT_TOKEN', ''):
            return

        import threading
        import logging
        logger = logging.getLogger(__name__)

        def polling_loop():
            import time
            import requests
            from django.db import connection as db_connection

            token     = settings.TELEGRAM_BOT_TOKEN
            proxy_url = getattr(settings, 'TELEGRAM_PROXY_URL', '')
            proxies   = {'https': proxy_url, 'http': proxy_url} if proxy_url else None

            # Удаляем webhook
            try:
                requests.post(
                    f'https://api.telegram.org/bot{token}/deleteWebhook',
                    json={'drop_pending_updates': True},
                    proxies=proxies, timeout=10
                )
                logger.info('Telegram webhook deleted, polling started')
            except Exception as e:
                logger.warning(f'Could not delete webhook: {e}')

            offset = 0
            consecutive_errors = 0

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
                    consecutive_errors = 0

                    if not data.get('ok'):
                        logger.error(f'getUpdates error: {data}')
                        time.sleep(5)
                        continue

                    for update in data.get('result', []):
                        try:
                            # Закрываем старое DB-соединение — Django откроет новое
                            db_connection.close_if_unusable_or_obsolete()
                            from core.telegram_bot import handle_update
                            handle_update(update)
                        except Exception as e:
                            logger.error(f'handle_update error: {e}')
                            try:
                                db_connection.close()
                            except Exception:
                                pass
                        offset = update['update_id'] + 1

                except requests.exceptions.Timeout:
                    continue

                except (requests.exceptions.SSLError,
                        requests.exceptions.ConnectionError) as e:
                    logger.warning(f'Network error in polling: {e}')
                    consecutive_errors += 1
                    time.sleep(min(consecutive_errors * 2, 30))

                except Exception as e:
                    logger.error(f'Polling error: {e}')
                    consecutive_errors += 1
                    time.sleep(min(consecutive_errors * 2, 30))

        t = threading.Thread(target=polling_loop, name='telegram-polling', daemon=True)
        t.start()
        logger.info('Telegram polling thread started')
