# Спасибо, коллега 🙏

Корпоративная платформа признания сотрудников на Django. Сотрудники
ежемесячно получают «монетки» и дарят их коллегам в знак благодарности,
а накопленные монетки можно обменять на награды. HR получает дашборд
с аналитикой по вовлечённости, неформальным лидерам, зоне выгорания,
сплочённости отделов и новичкам.

## Стек

- Python 3.11+, Django 5.0
- PostgreSQL (через `DATABASE_URL`)
- Bootstrap 5 (через CDN)
- Whitenoise для статики
- Gunicorn для продакшена

## Локальный запуск

```bash
# 1. Клонировать репозиторий и перейти в папку проекта
git clone <repo_url> spasibo-kollega
cd spasibo-kollega

# 2. Создать и активировать виртуальное окружение
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Настроить переменные окружения
cp .env.example .env
# отредактируйте .env: SECRET_KEY, DATABASE_URL и т.д.
# для локального запуска без PostgreSQL можно оставить DATABASE_URL пустым —
# тогда будет использован sqlite3

# 5. Применить миграции
python manage.py makemigrations
python manage.py migrate

# 6. Создать компанию, администратора и тестовые данные
python manage.py setup_company
# создаст компанию «ООО «Ромашка»», администратора admin@example.com / admin12345
# и 8 тестовых сотрудников с паролем employee12345

# 7. Собрать статику (для продакшена)
python manage.py collectstatic --noinput

# 8. Запустить сервер разработки
python manage.py runserver
```

Откройте http://127.0.0.1:8000/ — лендинг платформы.
Войдите как `admin@example.com` (пароль `admin12345`), чтобы увидеть HR-дашборд,
или как любой тестовый сотрудник, например `мария.ковалева@example.com`
(см. реальный список email в админке Django `/admin/`), пароль `employee12345`.

## Команды управления (management commands)

| Команда | Назначение | Когда запускать |
|---|---|---|
| `python manage.py setup_company` | Создаёт компанию, администратора, тестовые награды и сотрудников | Один раз при первом запуске |
| `python manage.py allocate_monthly_coins` | Начисляет всем активным сотрудникам по 30 монет (см. `MONTHLY_COIN_ALLOCATION` в settings) | 1-го числа каждого месяца (cron) |
| `python manage.py grant_anniversary_bonuses` | Начисляет бонусы за стаж (3/6/12/24/36 мес.) согласно `ANNIVERSARY_BONUSES` | Ежедневно (cron) |

### Пример cron-задач (на сервере)

```cron
# Ежемесячное начисление монет — 1-го числа в 06:00
0 6 1 * * cd /var/www/spasibo-kollega && /var/www/spasibo-kollega/venv/bin/python manage.py allocate_monthly_coins >> /var/log/spasibo_monthly.log 2>&1

# Бонусы за стаж — каждый день в 06:10
10 6 * * * cd /var/www/spasibo-kollega && /var/www/spasibo-kollega/venv/bin/python manage.py grant_anniversary_bonuses >> /var/log/spasibo_bonus.log 2>&1
```

## Бизнес-правила

- Каждый сотрудник получает `MONTHLY_COIN_ALLOCATION` (по умолчанию 30) монет
  ежемесячно через `allocate_monthly_coins`.
- Нельзя отправить монеты самому себе.
- Нельзя отправить больше, чем есть на балансе.
- Одному коллеге в течение месяца можно отправить не более
  `MAX_COINS_PER_RECEIVER_PER_MONTH` (по умолчанию 15) монет суммарно.
- Бонусы за стаж настраиваются в `ANNIVERSARY_BONUSES` (settings.py):
  `{3: 15, 6: 30, 12: 50, 24: 75, 36: 100}` месяцев → монет.

## Структура проекта

```
spasibo_kollega/
├── manage.py
├── requirements.txt
├── .env.example
├── config/                  # настройки Django
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── core/                     # основное приложение
│   ├── models.py             # Company, User, Reward, Transaction, ENPSSurvey
│   ├── views.py
│   ├── forms.py
│   ├── urls.py
│   ├── admin.py
│   ├── context_processors.py
│   └── management/commands/
│       ├── setup_company.py
│       ├── allocate_monthly_coins.py
│       └── grant_anniversary_bonuses.py
├── templates/core/           # HTML-шаблоны (Bootstrap 5)
└── static/css/style.css
```

## Деплой на Timeweb Cloud

1. Создайте облачное приложение (или сервер) с Python 3.11+ и подключите
   PostgreSQL — Timeweb выдаст строку подключения, поместите её в переменную
   окружения `DATABASE_URL` (формат `postgres://user:pass@host:5432/dbname`).
2. Задайте переменные окружения в панели управления (или в `.env` на сервере):
   `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS=ваш-домен.ru`,
   `CSRF_TRUSTED_ORIGINS=https://ваш-домен.ru`, `DATABASE_URL=...`.
3. Команда запуска (entrypoint):
   ```bash
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py collectstatic --noinput
   gunicorn config.wsgi:application --bind 0.0.0.0:8000
   ```
4. После первого деплоя выполните `python manage.py setup_company`
   (через консоль/SSH Timeweb), чтобы создать администратора компании.
5. Настройте cron-задачи `allocate_monthly_coins` и `grant_anniversary_bonuses`
   через раздел «Планировщик задач» в Timeweb Cloud.

## Точки роста

- JWT API для мобильного приложения / Telegram-бота (поле `telegram_chat_id`
  уже есть в модели `User`).
- Уведомления в Telegram о полученных монетках и приближении дедлайна
  ежемесячного начисления.
- Графики/визуализации для HR-дашборда (сплочённость отделов, динамика eNPS).
