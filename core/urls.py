from django.urls import path
from . import views
from . import telegram_views

urlpatterns = [
    # Публичные
    path('', views.landing, name='landing'),
    path('register/', views.register_company, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Сотрудник
    path('dashboard/', views.dashboard, name='dashboard'),
    path('give/', views.give_coins, name='give_coins'),
    path('feed/', views.feed, name='feed'),
    path('top/', views.top_employees, name='top_employees'),
    path('rewards/', views.rewards_shop, name='rewards_shop'),
    path('profile/', views.profile, name='profile'),

    # HR / Администратор
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),

    # Сотрудники
    path('admin-panel/employees/', views.admin_employees, name='admin_employees'),
    path('admin-panel/employees/add/', views.admin_employee_add, name='admin_employee_add'),
    path('admin-panel/employees/<int:user_id>/edit/', views.admin_employee_edit, name='admin_employee_edit'),
    path('admin-panel/employees/<int:user_id>/grant/', views.admin_grant_coins, name='admin_grant_coins'),
    path('admin-panel/employees/import/', views.admin_employee_import, name='admin_employee_import'),
    path('admin-panel/employees/import/template/', views.admin_employee_import_template, name='admin_employee_import_template'),

    # Награды
    path('admin-panel/rewards/', views.admin_rewards, name='admin_rewards'),
    path('admin-panel/rewards/<int:pk>/edit/', views.admin_reward_edit, name='admin_reward_edit'),

    # eNPS
    path('admin-panel/enps/', views.enps_start, name='enps_start'),
    path('admin-panel/enps/<int:pk>/', views.enps_detail, name='enps_detail'),
    path('enps/<int:pk>/respond/', views.enps_respond, name='enps_respond'),
    path('onboarding/', views.onboarding, name='onboarding'),
    # Пригласительные ссылки
    path('join/<str:token>/', views.invite_register, name='invite_register'),
    path('admin-panel/invites/', views.admin_invites, name='admin_invites'),

    # Заявки на награды
    path('admin-panel/reward-orders/', views.admin_reward_orders, name='admin_reward_orders'),

    # Бонусы за стаж
    path('admin-panel/seniority-bonuses/', views.admin_seniority_bonuses, name='admin_seniority_bonuses'),

    # Юридические страницы
    path('legal/privacy/', views.privacy, name='privacy'),
    path('legal/terms/', views.terms, name='terms'),

    # Поддержка
    path('support/', views.support_request, name='support_request'),

    # Telegram Bot
    path('api/telegram/webhook/', telegram_views.telegram_webhook, name='telegram_webhook'),
    path('api/telegram/link/', telegram_views.telegram_link, name='telegram_link'),
    path('api/telegram/unlink/', telegram_views.telegram_unlink, name='telegram_unlink'),
    path('api/telegram/setup-webhook/', telegram_views.setup_bot_webhook, name='telegram_setup'),

    # Cron-эндпоинты для cron-job.org
    path('api/cron/allocate-monthly-coins/', views.allocate_monthly_coins_api, name='allocate_monthly_coins'),
    path('api/cron/grant-anniversary-bonuses/', views.grant_anniversary_bonuses_api, name='grant_anniversary_bonuses'),
]
