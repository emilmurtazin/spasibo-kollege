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
    """Принимает апдейты от Telegram."""
    # Проверка секрета
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
    """Технический эндпоинт для регистрации webhook (только для суперпользователя)."""
    if not request.user.is_superuser:
        return HttpResponse(status=403)
    result = setup_webhook()
    return JsonResponse(result)
