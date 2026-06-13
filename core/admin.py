from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Company, User, Reward, Transaction, ENPSSurvey


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'subscription_plan', 'employee_limit', 'employees_count', 'created_at')
    list_filter = ('subscription_plan',)
    search_fields = ('name',)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'company', 'role', 'department', 'balance', 'is_staff')
    list_filter = ('company', 'role', 'department')
    fieldsets = UserAdmin.fieldsets + (
        ('Спасибо, коллега', {
            'fields': (
                'company', 'role', 'balance', 'department', 'hire_date',
                'current_goal', 'target_reward', 'telegram_chat_id',
                'last_monthly_allocation', 'last_bonus_date',
            )
        }),
    )


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'price', 'category', 'is_active')
    list_filter = ('company', 'category', 'is_active')
    search_fields = ('name',)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'from_user', 'to_user', 'amount', 'type', 'month', 'year')
    list_filter = ('type', 'year', 'month')
    search_fields = ('from_user__username', 'to_user__username', 'comment')


@admin.register(ENPSSurvey)
class ENPSSurveyAdmin(admin.ModelAdmin):
    list_display = ('company', 'started_at', 'average_score')
    list_filter = ('company',)
