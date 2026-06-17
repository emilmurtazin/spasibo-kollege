"""
Первоначальная настройка: создаёт компанию, суперпользователя-администратора
и набор тестовых данных (сотрудники, награды, транзакции).

Использование:
    python manage.py setup_company
    python manage.py setup_company --no-demo   # без тестовых данных
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.utils import timezone

from core.models import Company, User, Reward, Transaction


DEMO_EMPLOYEES = [
    ('Мария', 'Ковалёва', 'Frontend', 180),
    ('Дмитрий', 'Орлов', 'Backend', 90),
    ('Игорь', 'Петров', 'Продажи', 60),
    ('Елена', 'Семёнова', 'Поддержка', 400),
    ('Никита', 'Тарасов', 'HR', 20),
    ('Ольга', 'Лебедева', 'Аналитика', 1100),
    ('Сергей', 'Волков', 'Backend', 1300),
    ('Виктория', 'Титова', 'Frontend', 15),
]

DEMO_REWARDS = [
    ('Фирменный мерч (худи, кружка, стикеры)', 'Набор брендированного мерча компании.', 25, 'material'),
    ('Обед с руководителем', 'Личная встреча и обед с CEO или вашим руководителем.', 40, 'event'),
    ('Дополнительный выходной', 'Один дополнительный оплачиваемый день отдыха.', 100, 'wellbeing'),
    ('Курс на Stepik/Coursera', 'Любой онлайн-курс по вашему направлению развития.', 60, 'development'),
    ('Сертификат в кофейню', 'Сертификат на 1000 рублей в кофейню рядом с офисом.', 15, 'material'),
    ('Час с психологом/коучем', 'Индивидуальная консультация корпоративного психолога.', 30, 'wellbeing'),
]


class Command(BaseCommand):
    help = 'Создаёт компанию, суперпользователя-администратора и тестовые данные.'

    def add_arguments(self, parser):
        parser.add_argument('--company-name', default='ООО «Ромашка»', help='Название компании')
        parser.add_argument('--admin-email', default='admin@example.com', help='Email администратора')
        parser.add_argument('--admin-password', default='admin12345', help='Пароль администратора')
        parser.add_argument('--no-demo', action='store_true', help='Не создавать тестовых сотрудников/награды')

    def handle(self, *args, **options):
        today = timezone.now().date()

        company, created = Company.objects.get_or_create(
            name=options['company_name'],
            defaults={'subscription_plan': 'team', 'employee_limit': 150},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Компания «{company.name}» создана.'))
        else:
            self.stdout.write(f'Компания «{company.name}» уже существует, использую её.')

        admin_email = options['admin_email']
        if not User.objects.filter(email=admin_email).exists():
            admin = User.objects.create_superuser(
                username=admin_email,
                email=admin_email,
                password=options['admin_password'],
                first_name='Админ',
                last_name='Компании',
            )
            admin.company = company
            admin.role = 'admin'
            admin.department = 'Управление'
            admin.balance = 30
            admin.hire_date = today - timedelta(days=400)
            admin.last_monthly_allocation = today
            admin.save()
            self.stdout.write(self.style.SUCCESS(
                f'Суперпользователь создан: {admin_email} / {options["admin_password"]}'
            ))
        else:
            self.stdout.write(f'Пользователь с email {admin_email} уже существует, пропускаю.')

        if options['no_demo']:
            return

        # ----- Тестовые награды -----
        created_rewards = []
        for name, description, price, category in DEMO_REWARDS:
            reward, _ = Reward.objects.get_or_create(
                company=company, name=name,
                defaults={'description': description, 'price': price, 'category': category},
            )
            created_rewards.append(reward)
        self.stdout.write(self.style.SUCCESS(f'Награды готовы ({len(created_rewards)} шт.).'))

        # ----- Тестовые сотрудники -----
        demo_users = []
        for first_name, last_name, department, days_employed in DEMO_EMPLOYEES:
            email = f'{first_name.lower()}.{last_name.lower()}@example.com'.replace('ё', 'e')
            user, was_created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'company': company,
                    'department': department,
                    'role': 'employee',
                    'balance': 30,
                    'hire_date': today - timedelta(days=days_employed),
                    'last_monthly_allocation': today,
                },
            )
            if was_created:
                user.set_password('employee12345')
                user.save()
            demo_users.append(user)

        self.stdout.write(self.style.SUCCESS(f'Сотрудники готовы ({len(demo_users)} шт., пароль: employee12345).'))

        # ----- Несколько демонстрационных транзакций "Спасибо" -----
        if not Transaction.objects.filter(from_user__company=company, type='give').exists() and len(demo_users) >= 4:
            sample = [
                (demo_users[0], demo_users[1], 5, 'Спасибо за быстрый ревью пул-реквеста!'),
                (demo_users[2], demo_users[0], 10, 'Отличная презентация для клиента.'),
                (demo_users[3], demo_users[4], 3, 'Спасибо, что помогаешь новичкам освоиться.'),
                (demo_users[4], demo_users[2], 8, 'Классная идея по онбордингу.'),
            ]
            with db_transaction.atomic():
                for from_user, to_user, amount, comment in sample:
                    from_user.balance -= amount
                    to_user.balance += amount
                    from_user.save(update_fields=['balance'])
                    to_user.save(update_fields=['balance'])
                    Transaction.objects.create(
                        from_user=from_user, to_user=to_user, amount=amount,
                        comment=comment, type='give', month=today.month, year=today.year,
                    )
            self.stdout.write(self.style.SUCCESS('Демонстрационные транзакции созданы.'))

        self.stdout.write(self.style.SUCCESS('Готово! Можно входить под admin@example.com.'))
