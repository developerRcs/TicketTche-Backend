from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.audit.services import log_action

from .models import Ticket, TicketTransfer

User = get_user_model()


def get_user_tickets(user, status=None):
    qs = Ticket.objects.filter(owner=user).select_related(
        "event", "ticket_type", "owner"
    )
    if status:
        qs = qs.filter(status=status)
    return qs


def get_transfer(pk):
    return TicketTransfer.objects.select_related(
        "ticket", "from_user"
    ).get(pk=pk)


def initiate_transfer(ticket_id, to_email, from_user, request=None):
    from django.db import transaction

    with transaction.atomic():
        try:
            ticket = Ticket.objects.select_for_update().get(pk=ticket_id, owner=from_user)
        except Ticket.DoesNotExist:
            raise serializers.ValidationError({"ticket_id": "Ticket not found or not owned by you."})

        if ticket.status != Ticket.Status.ACTIVE:
            raise serializers.ValidationError({"ticket_id": "Ticket is not in active status."})

        if TicketTransfer.objects.filter(ticket=ticket, status=TicketTransfer.Status.PENDING).exists():
            raise serializers.ValidationError(
                {"ticket_id": "A pending transfer already exists for this ticket."}
            )

        if ticket.owner.email == to_email:
            raise serializers.ValidationError(
                {"to_email": "You cannot transfer a ticket to yourself."}
            )

        ticket.status = Ticket.Status.PENDING_TRANSFER
        ticket.save(update_fields=["status"])

        transfer = TicketTransfer.objects.create(
            ticket=ticket,
            from_user=from_user,
            to_email=to_email,
        )

    log_action(
        action="ticket_transfer_initiate",
        actor=from_user,
        target=ticket,
        metadata={"to_email": to_email},
        request=request,
    )
    return transfer


def accept_transfer(transfer_id, accepting_user, request=None):
    try:
        transfer = TicketTransfer.objects.get(pk=transfer_id, to_email=accepting_user.email)
    except TicketTransfer.DoesNotExist:
        raise serializers.ValidationError({"transfer_id": "Transfer not found."})

    if transfer.status != TicketTransfer.Status.PENDING:
        raise serializers.ValidationError({"transfer_id": "Transfer is not pending."})

    from django.utils import timezone
    if transfer.expires_at < timezone.now():
        raise serializers.ValidationError({"transfer_id": "Transfer has expired."})

    ticket = transfer.ticket
    ticket.owner = accepting_user
    ticket.status = Ticket.Status.ACTIVE
    ticket.save(update_fields=["owner", "status"])

    transfer.status = TicketTransfer.Status.ACCEPTED
    transfer.save(update_fields=["status"])

    log_action(
        action="ticket_transfer_accept",
        actor=accepting_user,
        target=ticket,
        request=request,
    )
    return transfer


def reject_transfer(transfer_id, rejecting_user, request=None):
    try:
        transfer = TicketTransfer.objects.get(pk=transfer_id, to_email=rejecting_user.email)
    except TicketTransfer.DoesNotExist:
        raise serializers.ValidationError({"transfer_id": "Transfer not found."})

    if transfer.status != TicketTransfer.Status.PENDING:
        raise serializers.ValidationError({"transfer_id": "Transfer is not pending."})

    ticket = transfer.ticket
    ticket.status = Ticket.Status.ACTIVE
    ticket.save(update_fields=["status"])

    transfer.status = TicketTransfer.Status.REJECTED
    transfer.save(update_fields=["status"])

    log_action(
        action="ticket_transfer_reject",
        actor=rejecting_user,
        target=ticket,
        request=request,
    )
    return transfer


def check_in_ticket(ticket_id, staff_user, request=None):
    """
    Validate and check-in a ticket. Prevents reuse — once used, ticket is marked as 'used'.
    Only staff/admin of the event's company can perform check-in.
    Uses select_for_update to prevent double check-in under concurrent requests.
    """
    from django.db import transaction

    with transaction.atomic():
        try:
            ticket = (
                Ticket.objects.select_for_update()
                .select_related("event__company", "owner", "ticket_type")
                .get(pk=ticket_id)
            )
        except Ticket.DoesNotExist:
            raise serializers.ValidationError({"ticket_id": "Ticket not found."})

        # Verify staff_user belongs to the event's company
        from apps.companies.models import CompanyMember

        if not staff_user.role in ("super_admin", "admin"):
            if not CompanyMember.objects.filter(
                user=staff_user,
                company=ticket.event.company,
            ).exists():
                raise serializers.ValidationError(
                    {"detail": "You are not authorized to check in tickets for this event."}
                )

        if ticket.status == Ticket.Status.USED:
            raise serializers.ValidationError(
                {
                    "ticket_id": "Ticket has already been used.",
                    "checked_in_at": ticket.checked_in_at.isoformat() if ticket.checked_in_at else None,
                }
            )

        if ticket.status == Ticket.Status.CANCELLED:
            raise serializers.ValidationError({"ticket_id": "Ticket is cancelled."})

        if ticket.status == Ticket.Status.TRANSFERRED:
            raise serializers.ValidationError({"ticket_id": "Ticket has been transferred."})

        if ticket.status == Ticket.Status.PENDING_TRANSFER:
            raise serializers.ValidationError(
                {"ticket_id": "Ticket has a pending transfer and cannot be used."}
            )

        from django.utils import timezone

        ticket.status = Ticket.Status.USED
        ticket.checked_in_at = timezone.now()
        ticket.save(update_fields=["status", "checked_in_at"])

    log_action(
        action="ticket_check_in",
        actor=staff_user,
        target=ticket,
        metadata={"event_id": str(ticket.event.id), "owner_email": ticket.owner.email},
        request=request,
    )
    return ticket


def cancel_transfer(transfer_id, cancelling_user, request=None):
    try:
        transfer = TicketTransfer.objects.get(pk=transfer_id, from_user=cancelling_user)
    except TicketTransfer.DoesNotExist:
        raise serializers.ValidationError({"transfer_id": "Transfer not found."})

    if transfer.status != TicketTransfer.Status.PENDING:
        raise serializers.ValidationError({"transfer_id": "Transfer is not pending."})

    ticket = transfer.ticket
    ticket.status = Ticket.Status.ACTIVE
    ticket.save(update_fields=["status"])

    transfer.status = TicketTransfer.Status.CANCELLED
    transfer.save(update_fields=["status"])

    log_action(
        action="ticket_transfer_cancel",
        actor=cancelling_user,
        target=ticket,
        request=request,
    )
    return transfer
