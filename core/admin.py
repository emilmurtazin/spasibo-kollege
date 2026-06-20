from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Company, User, Reward, Transaction, ENPSSurvey, CompanyInvite, TelegramLinkToken, SeniorityBonus, SeniorityBonusGrant


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


@admin.register(CompanyInvite)
class CompanyInviteAdmin(admin.ModelAdmin):
    list_display = ('company', 'token', 'created_by', 'created_at', 'expires_at', 'uses_count', 'is_active')
    list_filter = ('company', 'is_active')


@admin.register(TelegramLinkToken)
class TelegramLinkTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'created_at', 'used')
    list_filter = ('used',)


@admin.register(SeniorityBonus)
class SeniorityBonusAdmin(admin.ModelAdmin):
    list_display = ('company', 'days_required', 'coins_amount', 'is_active')
    list_filter = ('company', 'is_active')


@admin.register(SeniorityBonusGrant)
class SeniorityBonusGrantAdmin(admin.ModelAdmin):
    list_display = ('user', 'bonus', 'granted_at')
    list_filter = ('bonus__company',)
