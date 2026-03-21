from celery import shared_task


@shared_task
def cancel_expired_orders():
    from .services import cancel_expired_orders as _cancel
    count = _cancel()
    return f"Cancelled {count} expired orders"
