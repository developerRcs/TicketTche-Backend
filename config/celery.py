import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("tickettche")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "expire-pending-transfers": {
        "task": "apps.tickets.tasks.expire_pending_transfers",
        "schedule": crontab(minute="*/5"),
    },
    "cancel-expired-orders": {
        "task": "apps.orders.tasks.cancel_expired_orders",
        "schedule": crontab(minute="*/5"),
    },
    "send-pending-order-reminders": {
        "task": "apps.orders.tasks.send_pending_order_reminders",
        "schedule": crontab(minute="*/30"),
    },
    "process-pending-withdrawals": {
        "task": "apps.withdrawals.tasks.process_pending_withdrawals",
        "schedule": crontab(minute=0),  # every hour
    },
}
