"""
Webhook и вспомогательные views для Telegram-бота.
"""
import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages

from .telegram_bot import handle_update, setup_webhook
from .models import TelegramLinkToken

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def telegram_webhook(request):
    """
    Принимает апдейты от Telegram и обрабатывает синхронно.

    Threading не используем — Gunicorn sync-воркеры убивают фоновые потоки
    до их завершения. Скорость обеспечивается коротким таймаутом в _api().
    """
    secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    if secret != settings.TELEGRAM_WEBHOOK_SECRET:
        return HttpResponse(status=403)

    try:
        update = json.loads(request.body)
        handle_update(update)
    except Exception as e:
        logger.error(f'Webhook error: {e}')

    return HttpResponse('ok')


@login_required
def telegram_link(request):
    """Генерирует токен и возвращает ссылку для привязки Telegram."""
    user  = request.user
    token = TelegramLinkToken.generate_for(user)

    bot_username = settings.TELEGRAM_BOT_USERNAME  # задать в .env
    link = f'https://t.me/{bot_username}?start={token.token}'

    return JsonResponse({'link': link, 'token': token.token})


@login_required
def telegram_unlink(request):
    """Отвязать Telegram от аккаунта."""
    if request.method == 'POST':
        request.user.telegram_chat_id = None
        request.user.save(update_fields=['telegram_chat_id'])
        TelegramLinkToken.objects.filter(user=request.user).delete()
        messages.success(request, 'Telegram отвязан от аккаунта.')
    return redirect('profile')


def setup_bot_webhook(request):
    """Регистрация webhook в Telegram. Доступно HR-администратору компании."""
    if not request.user.is_authenticated or request.user.role != 'admin':
        from django.http import HttpResponse
        return HttpResponse('Доступ запрещён. Войдите как администратор.', status=403)

    result = setup_webhook()
    ok = result.get('ok', False)

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Telegram Webhook</title>
  <style>
    body {{font-family:-apple-system,sans-serif;max-width:480px;margin:60px auto;padding:0 24px;text-align:center;}}
    .icon {{font-size:3rem;margin-bottom:16px;}}
    h1 {{font-size:1.3rem;margin:0 0 12px;}}
    p {{color:#6e6e73;font-size:.95rem;line-height:1.6;}}
    pre {{background:#f5f5f7;border-radius:10px;padding:14px;font-size:.78rem;text-align:left;overflow-x:auto;}}
    a {{display:inline-block;margin-top:20px;padding:10px 24px;background:#1d1d1f;color:#fff;border-radius:10px;text-decoration:none;font-size:.9rem;}}
  </style>
</head>
<body>
  <div class="icon">{'✅' if ok else '❌'}</div>
  <h1>{'Webhook установлен!' if ok else 'Ошибка установки webhook'}</h1>
  <p>{'Telegram будет отправлять сообщения боту на ваш сервер. Бот готов к работе.' if ok else 'Проверьте что TELEGRAM_BOT_TOKEN задан правильно в переменных окружения.'}</p>
  <pre>{json.dumps(result, ensure_ascii=False, indent=2)}</pre>
  <a href="/dashboard/">← Вернуться на главную</a>
</body>
</html>"""

    from django.http import HttpResponse
    return HttpResponse(html)
