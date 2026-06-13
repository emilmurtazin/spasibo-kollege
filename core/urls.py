from django.urls import path
from . import views

urlpatterns = [
    # Публичные страницы
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

    # Администратор / HR
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/employees/', views.admin_employees, name='admin_employees'),
    path('admin-panel/employees/<int:user_id>/grant/', views.admin_grant_coins, name='admin_grant_coins'),
    path('admin-panel/rewards/', views.admin_rewards, name='admin_rewards'),
    path('admin-panel/rewards/<int:pk>/edit/', views.admin_reward_edit, name='admin_reward_edit'),

    # eNPS
    path('admin-panel/enps/', views.enps_start, name='enps_start'),
    path('admin-panel/enps/<int:pk>/', views.enps_detail, name='enps_detail'),
    path('enps/<int:pk>/respond/', views.enps_respond, name='enps_respond'),
]
