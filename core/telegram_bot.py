"""
Telegram-бот «Спасибо, коллега».

Функции:
  /start          — привязка Telegram-аккаунта к профилю платформы
  /give           — отправить монетки коллеге
  /balance        — посмотреть баланс
  /help           — список команд

Уведомления (вызываются из views.py при событиях):
  notify_coins_received()  — кто-то подарил монетки
  notify_reward_available() — накоплено достаточно для награды
  notify_month_reminder()  — напоминание в конце месяца
"""

import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Низкоуровневый API-клиент
# ---------------------------------------------------------------------------

def _api(method: str, **kwargs) -> dict:
    """Вызов Telegram Bot API.

    Запросы идут через прокси (settings.TELEGRAM_PROXY_URL), так как
    api.telegram.org недоступен напрямую с некоторых российских хостингов
    из-за блокировок на уровне магистральных провайдеров.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning('TELEGRAM_BOT_TOKEN не задан')
        return {}
    url = f'https://api.telegram.org/bot{token}/{method}'

    proxy_url = getattr(settings, 'TELEGRAM_PROXY_URL', '')
    proxies = {'https': proxy_url, 'http': proxy_url} if proxy_url else None

    try:
        r = requests.post(url, json=kwargs, timeout=10, proxies=proxies)
        return r.json()
    except Exception as e:
        logger.error(f'Telegram API error ({method}): {e}')
        return {}


def send_message(chat_id: int, text: str, reply_markup=None, parse_mode='HTML') -> dict:
    """Отправить сообщение пользователю."""
    kwargs = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}
    if reply_markup:
        kwargs['reply_markup'] = reply_markup
    return _api('sendMessage', **kwargs)


def answer_callback(callback_query_id: str, text: str = '') -> dict:
    return _api('answerCallbackQuery', callback_query_id=callback_query_id, text=text)


def setup_webhook() -> dict:
    """Зарегистрировать webhook в Telegram. Вызывать один раз при деплое."""
    site_url  = settings.SITE_URL.rstrip('/')
    secret    = settings.TELEGRAM_WEBHOOK_SECRET
    webhook   = f'{site_url}/api/telegram/webhook/'
    return _api('setWebhook', url=webhook, secret_token=secret)


# ---------------------------------------------------------------------------
# Inline-клавиатуры
# ---------------------------------------------------------------------------

def kb_inline(buttons: list) -> dict:
    """
    buttons = [[('Текст', 'callback_data'), ...], ...]
    """
    return {
        'inline_keyboard': [
            [{'text': t, 'callback_data': d} for t, d in row]
            for row in buttons
        ]
    }


def kb_reply(rows: list) -> dict:
    """Обычная клавиатура."""
    return {
        'keyboard': [[{'text': t} for t in row] for row in rows],
        'resize_keyboard': True,
        'one_time_keyboard': False,
    }


# ---------------------------------------------------------------------------
# Уведомления (вызываются из Django-кода)
# ---------------------------------------------------------------------------

def notify_coins_received(to_user, from_user, amount: int, comment: str = ''):
    """Уведомить получателя монеток."""
    if not to_user.telegram_chat_id:
        return
    text = (
        f'🎉 <b>{from_user.get_full_name() or from_user.username}</b> '
        f'подарил(а) вам <b>{amount}</b> монеток!\n'
    )
    if comment:
        text += f'\n💬 «{comment}»\n'
    text += f'\n💰 Ваш баланс: <b>{to_user.balance}</b> монеток'
    if to_user.target_reward:
        text += f'\n🎯 Цель «{to_user.target_reward.name}»: ещё {max(0, to_user.target_reward.price - to_user.balance)} монеток'
    send_message(to_user.telegram_chat_id, text)


def notify_reward_available(user):
    """Уведомить когда накоплено достаточно для награды."""
    if not user.telegram_chat_id or not user.target_reward:
        return
    if user.balance >= user.target_reward.price:
        text = (
            f'🏆 Поздравляем! У вас достаточно монеток для награды\n'
            f'<b>«{user.target_reward.name}»</b>\n\n'
            f'Перейдите в магазин наград, чтобы получить её:\n'
            f'{settings.SITE_URL}/rewards/'
        )
        send_message(user.telegram_chat_id, text)


def notify_month_reminder(user, days_left: int = 3):
    """Напоминание в конце месяца об остатке монеток."""
    if not user.telegram_chat_id:
        return
    if user.balance > 0:
        text = (
            f'⏰ До конца месяца осталось <b>{days_left} дня</b>.\n'
            f'У вас ещё <b>{user.balance} монеток</b> для подарка коллегам.\n'
            f'Неиспользованные монетки сгорают!\n\n'
            f'Подарить: {settings.SITE_URL}/give/'
        )
        send_message(user.telegram_chat_id, text)


# ---------------------------------------------------------------------------
# Обработчик входящих сообщений (webhook)
# ---------------------------------------------------------------------------

def handle_update(update: dict):
    """Главный диспетчер входящих апдейтов от Telegram."""

    # Callback от inline-кнопок
    if 'callback_query' in update:
        _handle_callback(update['callback_query'])
        return

    message = update.get('message') or update.get('edited_message')
    if not message:
        return

    chat_id = message['chat']['id']
    text    = (message.get('text') or '').strip()

    if text.startswith('/start'):
        _cmd_start(chat_id, message, text)
    elif text.startswith('/give') or text == '💛 Подарить монетки':
        _cmd_give_start(chat_id, message)
    elif text.startswith('/balance') or text == '💰 Мой баланс':
        _cmd_balance(chat_id, message)
    elif text.startswith('/help') or text == '❓ Помощь':
        _cmd_help(chat_id)
    else:
        # Проверяем — вдруг пользователь в середине диалога
        _handle_dialog(chat_id, message, text)


# ---------------------------------------------------------------------------
# Команды
# ---------------------------------------------------------------------------

def _cmd_start(chat_id: int, message: dict, text: str):
    """
    /start          — просто начать (для зарегистрированных)
    /start TOKEN    — привязка аккаунта по одноразовому токену
    """
    from .models import User, TelegramLinkToken

    parts = text.split()
    token_value = parts[1] if len(parts) > 1 else None

    tg_user = message.get('from', {})
    tg_name = tg_user.get('first_name', 'друг')

    # Попытка привязки по токену
    if token_value:
        try:
            link = TelegramLinkToken.objects.select_related('user').get(
                token=token_value, used=False
            )
            user = link.user
            user.telegram_chat_id = chat_id
            user.save(update_fields=['telegram_chat_id'])
            link.used = True
            link.save(update_fields=['used'])

            text_out = (
                f'✅ Отлично, {tg_name}!\n\n'
                f'Ваш Telegram привязан к аккаунту <b>{user.get_full_name() or user.email}</b>.\n'
                f'Теперь вы будете получать уведомления о монетках здесь.\n\n'
                f'Баланс: <b>{user.balance}</b> монеток'
            )
            send_message(chat_id, text_out, reply_markup=_main_keyboard())
            return
        except Exception:
            send_message(chat_id, '❌ Ссылка недействительна или уже использована.')
            return

    # Проверяем — уже привязан?
    user = User.objects.filter(telegram_chat_id=chat_id).first()
    if user:
        send_message(
            chat_id,
            f'👋 С возвращением, <b>{user.get_full_name() or user.email}</b>!\n'
            f'Баланс: <b>{user.balance}</b> монеток',
            reply_markup=_main_keyboard()
        )
    else:
        site = settings.SITE_URL
        send_message(
            chat_id,
            f'👋 Привет, {tg_name}!\n\n'
            f'Я бот платформы <b>«Спасибо, коллега»</b>.\n\n'
            f'Чтобы привязать Telegram к вашему аккаунту:\n'
            f'1. Войдите на <a href="{site}">{site}</a>\n'
            f'2. Перейдите в Профиль → «Привязать Telegram»\n'
            f'3. Нажмите кнопку — и получите ссылку для подтверждения',
            reply_markup=kb_inline([[('🔗 Перейти на сайт', f'open_site')]])
        )


def _cmd_balance(chat_id: int, message: dict):
    from .models import User
    user = User.objects.filter(telegram_chat_id=chat_id).first()
    if not user:
        _not_linked(chat_id)
        return
    text = f'💰 Ваш баланс: <b>{user.balance}</b> монеток\n'
    if user.target_reward:
        remaining = max(0, user.target_reward.price - user.balance)
        text += f'\n🎯 Цель: «{user.target_reward.name}»\nОсталось накопить: <b>{remaining}</b> монеток'
    send_message(chat_id, text, reply_markup=_main_keyboard())


def _cmd_give_start(chat_id: int, message: dict):
    from .models import User
    user = User.objects.filter(telegram_chat_id=chat_id).first()
    if not user:
        _not_linked(chat_id)
        return

    # Показываем список коллег кнопками (первые 10 по алфавиту)
    colleagues = User.objects.filter(
        company=user.company, is_active=True
    ).exclude(pk=user.pk).order_by('first_name', 'last_name')[:10]

    if not colleagues:
        send_message(chat_id, '😕 В вашей компании пока нет других сотрудников.')
        return

    buttons = [
        [(f'{c.get_full_name() or c.email}', f'give_to:{c.pk}')]
        for c in colleagues
    ]
    send_message(
        chat_id,
        f'💛 Кому подарить монетки?\n\n(баланс: <b>{user.balance}</b>)',
        reply_markup=kb_inline(buttons)
    )


def _cmd_help(chat_id: int):
    text = (
        '<b>Команды бота:</b>\n\n'
        '/balance — посмотреть баланс\n'
        '/give — подарить монетки коллеге\n'
        '/help — эта справка\n\n'
        f'Платформа: <a href="{settings.SITE_URL}">{settings.SITE_URL}</a>'
    )
    send_message(chat_id, text, reply_markup=_main_keyboard())


# ---------------------------------------------------------------------------
# Callback-кнопки (inline)
# ---------------------------------------------------------------------------

_GIVE_SESSIONS = {}   # chat_id → {'to_user_id': ..., 'amount': ...}


def _handle_callback(cq: dict):
    from .models import User
    chat_id = cq['message']['chat']['id']
    cq_id   = cq['id']
    data    = cq.get('data', '')

    if data == 'open_site':
        answer_callback(cq_id)
        return

    # Выбор получателя
    if data.startswith('give_to:'):
        to_user_id = int(data.split(':')[1])
        _GIVE_SESSIONS[chat_id] = {'to_user_id': to_user_id, 'step': 'amount'}
        to_user = User.objects.filter(pk=to_user_id).first()
        answer_callback(cq_id)
        send_message(
            chat_id,
            f'Выбран: <b>{to_user.get_full_name() or to_user.email}</b>\n\nСколько монеток подарить?',
            reply_markup=kb_inline([
                [('1', 'amount:1'), ('3', 'amount:3'), ('5', 'amount:5')],
                [('7', 'amount:7'), ('10', 'amount:10'), ('15', 'amount:15')],
            ])
        )
        return

    # Выбор количества
    if data.startswith('amount:'):
        session = _GIVE_SESSIONS.get(chat_id, {})
        if not session:
            answer_callback(cq_id, 'Сессия истекла, начните заново /give')
            return
        amount = int(data.split(':')[1])
        session['amount'] = amount
        session['step']   = 'comment'
        _GIVE_SESSIONS[chat_id] = session
        answer_callback(cq_id)
        send_message(
            chat_id,
            f'Отлично! <b>{amount}</b> монеток.\n\n'
            f'Напишите сообщение (за что благодарите) или нажмите «Пропустить»:',
            reply_markup=kb_inline([[('Пропустить →', 'comment:skip')]])
        )
        return

    # Пропустить комментарий
    if data == 'comment:skip':
        answer_callback(cq_id)
        _finalize_give(chat_id, comment='')
        return

    answer_callback(cq_id)


def _handle_dialog(chat_id: int, message: dict, text: str):
    """Обрабатывает свободный текст — например, комментарий к подарку."""
    session = _GIVE_SESSIONS.get(chat_id, {})
    if session.get('step') == 'comment':
        _finalize_give(chat_id, comment=text)


def _finalize_give(chat_id: int, comment: str):
    """Финальный шаг — списать монетки и записать транзакцию."""
    from django.db import transaction as db_tx
    from django.utils import timezone
    from .models import User, Transaction
    from django.conf import settings as s

    session = _GIVE_SESSIONS.pop(chat_id, {})
    if not session:
        send_message(chat_id, '❌ Сессия истекла. Начните заново: /give')
        return

    from_user = User.objects.filter(telegram_chat_id=chat_id).first()
    to_user   = User.objects.filter(pk=session['to_user_id']).first()
    amount    = session.get('amount', 1)

    if not from_user or not to_user:
        send_message(chat_id, '❌ Ошибка: пользователь не найден.')
        return

    if from_user.balance < amount:
        send_message(chat_id,
            f'❌ Недостаточно монеток. Баланс: <b>{from_user.balance}</b>, нужно: <b>{amount}</b>',
            reply_markup=_main_keyboard()
        )
        return

    # Проверка лимита 15 монет одному коллеге в месяц
    today = timezone.now().date()
    already = from_user.coins_given_to(to_user, today.year, today.month)
    limit   = s.MAX_COINS_PER_RECEIVER_PER_MONTH
    if already + amount > limit:
        remaining = max(0, limit - already)
        send_message(chat_id,
            f'❌ Лимит {limit} монеток одному коллеге в месяц.\n'
            f'Уже отправлено: {already}, можно ещё: {remaining}',
            reply_markup=_main_keyboard()
        )
        return

    with db_tx.atomic():
        from_user.balance -= amount
        from_user.save(update_fields=['balance'])
        to_user.balance += amount
        to_user.save(update_fields=['balance'])
        Transaction.objects.create(
            from_user=from_user, to_user=to_user,
            amount=amount, comment=comment, type='give',
            month=today.month, year=today.year,
        )

    # Подтверждение отправителю
    send_message(
        chat_id,
        f'✅ Готово! <b>{amount}</b> монеток подарено '
        f'<b>{to_user.get_full_name() or to_user.email}</b>.\n'
        f'{"💬 «" + comment + "»" if comment else ""}\n\n'
        f'Остаток: <b>{from_user.balance}</b> монеток',
        reply_markup=_main_keyboard()
    )

    # Уведомление получателю
    notify_coins_received(to_user, from_user, amount, comment)

    # Проверка достижения цели
    notify_reward_available(to_user)


# ---------------------------------------------------------------------------
# Вспомогательные
# ---------------------------------------------------------------------------

def _main_keyboard():
    return kb_reply([
        ['💛 Подарить монетки', '💰 Мой баланс'],
        ['❓ Помощь'],
    ])


def _not_linked(chat_id: int):
    site = settings.SITE_URL
    send_message(
        chat_id,
        f'⚠️ Ваш Telegram не привязан к аккаунту.\n\n'
        f'Войдите на {site}, перейдите в Профиль → «Привязать Telegram».',
    )
