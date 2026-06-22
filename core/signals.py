"""
Сигналы Django.

Автоматическая проверка/смена тарифа компании при любом изменении
числа активных сотрудников — срабатывает централизованно при каждом
save() модели User, независимо от того, в каком view это произошло
(добавление вручную, bulk, импорт, приглашение, деактивация и т.д.).

Так надёжнее, чем расставлять вызов check_and_update_plan() вручную
в каждом view — гарантирует, что проверка не будет забыта при будущих
изменениях кода.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User


@receiver(post_save, sender=User)
def auto_adjust_company_plan(sender, instance, **kwargs):
    """При сохранении сотрудника — проверить и при необходимости сменить тариф компании."""
    if not instance.company_id:
        return
    try:
        instance.company.check_and_update_plan()
    except Exception:
        # Не должно ронять основной запрос (создание/редактирование сотрудника),
        # даже если в подсчёте тарифа что-то пошло не так.
        import logging
        logging.getLogger(__name__).exception('Ошибка автообновления тарифа компании')
