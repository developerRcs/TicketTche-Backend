from celery import shared_task
from django.utils import timezone


@shared_task
def expire_pending_transfers():
    from .models import Ticket, TicketTransfer

    expired = TicketTransfer.objects.filter(
        status=TicketTransfer.Status.PENDING,
        expires_at__lt=timezone.now(),
    ).select_related("ticket")

    count = 0
    for transfer in expired:
        transfer.status = TicketTransfer.Status.CANCELLED
        transfer.save(update_fields=["status"])
        ticket = transfer.ticket
        ticket.status = Ticket.Status.ACTIVE
        ticket.save(update_fields=["status"])
        count += 1

    return f"Expired {count} transfers"
