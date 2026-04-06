from datetime import timedelta

from celery import shared_task
from django.utils import timezone


@shared_task
def cancel_expired_orders():
    from .services import cancel_expired_orders as _cancel
    count = _cancel()
    return f"Cancelled {count} expired orders"


@shared_task
def send_payment_failed_email_task(order_id: str):
    from .emails import send_payment_failed_email
    from .models import Order

    try:
        order = Order.objects.select_related("buyer", "event").get(pk=order_id)
    except Order.DoesNotExist:
        return f"Order {order_id} not found"

    send_payment_failed_email(order)
    return f"Payment failed email sent for order {order_id}"


@shared_task
def send_pending_order_reminders():
    """
    Called every 30 minutes by beat.
    Sends ONE reminder per pending order — uses reminder_sent_at to prevent
    spam (never sends more than one reminder per order regardless of how long
    it stays pending).
    """
    from .emails import send_pending_order_reminder_email
    from .models import Order

    two_hours_ago = timezone.now() - timedelta(hours=2)
    five_minutes_from_now = timezone.now() + timedelta(minutes=5)

    # Only orders that:
    # - are still pending
    # - have been pending for > 2 hours (not brand new)
    # - still have at least 5 minutes before expiry (no point reminding if almost expired)
    # - have NOT yet received a reminder (reminder_sent_at is null)
    orders = Order.objects.select_related("buyer", "event").filter(
        status=Order.Status.PENDING,
        created_at__lt=two_hours_ago,
        expires_at__gt=five_minutes_from_now,
        reminder_sent_at__isnull=True,
    )

    count = 0
    for order in orders:
        try:
            send_pending_order_reminder_email(order)
            order.reminder_sent_at = timezone.now()
            order.save(update_fields=["reminder_sent_at"])
            count += 1
        except Exception:
            pass

    return f"Pending order reminders sent: {count}"
