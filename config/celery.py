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
}
