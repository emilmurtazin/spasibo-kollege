from django.conf import settings


def company_context(request):
    """Добавляет в контекст шаблонов компанию текущего пользователя и тарифные планы."""
    company = None
    if request.user.is_authenticated:
        company = getattr(request.user, 'company', None)
    return {
        'current_company': company,
        'subscription_plans': settings.SUBSCRIPTION_PLANS,
    }
