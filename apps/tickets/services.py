import json
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
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
    else:
        # Default: only show active tickets (payment confirmed)
        qs = qs.filter(status__in=["active", "pending_transfer"])
    return qs


def get_transfer(pk):
    return TicketTransfer.objects.select_related(
        "ticket", "from_user"
    ).get(pk=pk)


def initiate_transfer(ticket_id, to_email, from_user, agreed_price=None, request=None):
    from decimal import Decimal
    from django.db import transaction
    from django.core.mail import send_mail
    from django.conf import settings

    with transaction.atomic():
        try:
            ticket = Ticket.objects.select_for_update().select_related("ticket_type").get(
                pk=ticket_id, owner=from_user
            )
        except Ticket.DoesNotExist:
            raise serializers.ValidationError({"ticket_id": "Ingresso não encontrado ou não pertence a você."})

        if ticket.status != Ticket.Status.ACTIVE:
            raise serializers.ValidationError({"ticket_id": "O ingresso não está ativo."})

        if TicketTransfer.objects.filter(ticket=ticket, status=TicketTransfer.Status.PENDING).exists():
            raise serializers.ValidationError(
                {"ticket_id": "Já existe uma transferência pendente para este ingresso."}
            )

        if ticket.owner.email == to_email:
            raise serializers.ValidationError(
                {"to_email": "Você não pode transferir um ingresso para si mesmo."}
            )

        # Validate agreed_price within ±10% of original price
        if agreed_price is not None:
            original_price = Decimal(str(ticket.ticket_type.price))
            agreed = Decimal(str(agreed_price))
            min_price = (original_price * Decimal("0.90")).quantize(Decimal("0.01"))
            max_price = (original_price * Decimal("1.10")).quantize(Decimal("0.01"))
            if agreed < min_price or agreed > max_price:
                raise serializers.ValidationError(
                    {
                        "agreed_price": (
                            f"O valor combinado deve estar entre "
                            f"R$ {min_price} e R$ {max_price} "
                            f"(±10% do valor original de R$ {original_price})."
                        )
                    }
                )

        ticket.status = Ticket.Status.PENDING_TRANSFER
        ticket.save(update_fields=["status"])

        # Calculate platform fee (8% of agreed_price)
        platform_fee = None
        if agreed_price is not None:
            platform_fee = (Decimal(str(agreed_price)) * Decimal("0.08")).quantize(Decimal("0.01"))

        transfer = TicketTransfer.objects.create(
            ticket=ticket,
            from_user=from_user,
            to_email=to_email,
            agreed_price=agreed_price,
            platform_fee=platform_fee,
        )

    # Send confirmation code to owner by email
    try:
        send_mail(
            subject="TicketTchê — Confirme a transferência do seu ingresso",
            message=(
                f"Olá {from_user.first_name},\n\n"
                f"Você solicitou a transferência do ingresso para \"{ticket.event.title}\" "
                f"para {to_email}.\n\n"
                f"Seu código de confirmação é: {transfer.confirmation_code}\n\n"
                f"Este código expira em 48 horas.\n"
                f"Se você não solicitou esta transferência, ignore este email.\n\n"
                f"TicketTchê"
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@tickettche.com.br"),
            recipient_list=[from_user.email],
            fail_silently=True,
        )
    except Exception:
        pass

    log_action(
        action="ticket_transfer_initiate",
        actor=from_user,
        target=ticket,
        metadata={"to_email": to_email, "agreed_price": str(agreed_price) if agreed_price else None},
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

    if not transfer.owner_confirmed:
        raise serializers.ValidationError(
            {"transfer_id": "O dono do ingresso ainda não confirmou a transferência."}
        )

    from django.utils import timezone
    if transfer.expires_at < timezone.now():
        raise serializers.ValidationError({"transfer_id": "Transfer has expired."})

    # Don't change ticket ownership here — it happens in confirm_transfer_payment
    # Don't change ticket status here — keep it PENDING_TRANSFER until payment
    transfer.status = TicketTransfer.Status.ACCEPTED
    transfer.save(update_fields=["status"])

    log_action(
        action="ticket_transfer_accept",
        actor=accepting_user,
        target=transfer.ticket,
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


def confirm_transfer_by_owner(transfer_id, confirmation_code, owner_user, request=None):
    """
    Owner confirms the transfer initiation using the emailed code.
    After owner confirmation, receiver is notified (or invited if no account).
    """
    from django.contrib.auth import get_user_model
    from django.core.mail import send_mail
    from django.conf import settings

    User = get_user_model()

    try:
        transfer = TicketTransfer.objects.select_related(
            "ticket__event", "from_user"
        ).get(pk=transfer_id, from_user=owner_user)
    except TicketTransfer.DoesNotExist:
        raise serializers.ValidationError({"transfer_id": "Transferência não encontrada."})

    if transfer.status != TicketTransfer.Status.PENDING:
        raise serializers.ValidationError({"transfer_id": "Esta transferência não está pendente."})

    if transfer.owner_confirmed:
        raise serializers.ValidationError({"transfer_id": "Transferência já confirmada pelo dono."})

    from django.utils import timezone
    if transfer.expires_at < timezone.now():
        raise serializers.ValidationError({"transfer_id": "Esta transferência expirou."})

    if transfer.confirmation_code != str(confirmation_code).strip():
        raise serializers.ValidationError({"confirmation_code": "Código de confirmação inválido."})

    transfer.owner_confirmed = True
    transfer.save(update_fields=["owner_confirmed"])

    # Generate opaque invite token stored in Redis
    frontend_url = getattr(settings, "FRONTEND_URL", "https://tickettche.com.br")
    invite_token = secrets.token_urlsafe(32)
    cache.set(
        f"ticket:transfer:invite:{invite_token}",
        json.dumps({"transfer_id": str(transfer.id), "to_email": transfer.to_email}),
        timeout=48 * 3600,
    )
    invite_url = f"{frontend_url}/aceitar-ingresso/{invite_token}"

    receiver_exists = User.objects.filter(email=transfer.to_email).exists()

    context = {
        "sender_name": owner_user.first_name or owner_user.email,
        "event_title": transfer.ticket.event.title,
        "agreed_price": transfer.agreed_price,
        "invite_url": invite_url,
        "to_email": transfer.to_email,
    }

    if receiver_exists:
        subject = "TicketTchê — Você recebeu uma transferência de ingresso"
        template_name = "tickets/emails/transfer_notification.html"
    else:
        subject = "TicketTchê — Você foi convidado a receber um ingresso"
        template_name = "tickets/emails/transfer_invitation.html"

    html_content = render_to_string(template_name, context)
    text_content = (
        f"{context['sender_name']} quer te transferir um ingresso para {context['event_title']}.\n"
        f"Acesse: {invite_url}"
    )

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@tickettche.com.br"),
        to=[transfer.to_email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=True)

    log_action(
        action="ticket_transfer_owner_confirmed",
        actor=owner_user,
        target=transfer.ticket,
        metadata={"to_email": transfer.to_email, "receiver_exists": receiver_exists},
        request=request,
    )
    return transfer


def confirm_transfer_payment(transfer_id, accepting_user, request=None):
    """
    Receiver confirms that payment was made to the original owner.
    This finalizes the transfer: ticket ownership changes and ticket becomes ACTIVE.
    """
    try:
        transfer = TicketTransfer.objects.select_related("ticket").get(
            pk=transfer_id, to_email=accepting_user.email
        )
    except TicketTransfer.DoesNotExist:
        raise serializers.ValidationError({"transfer_id": "Transferência não encontrada."})

    if transfer.status != TicketTransfer.Status.ACCEPTED:
        raise serializers.ValidationError(
            {"transfer_id": "A transferência deve ser aceita antes de confirmar o pagamento."}
        )

    if transfer.payment_confirmed:
        raise serializers.ValidationError({"transfer_id": "Pagamento já confirmado."})

    transfer.payment_confirmed = True
    transfer.save(update_fields=["payment_confirmed"])

    ticket = transfer.ticket
    ticket.owner = accepting_user
    ticket.status = Ticket.Status.ACTIVE
    ticket.save(update_fields=["owner", "status"])

    log_action(
        action="ticket_transfer_payment_confirmed",
        actor=accepting_user,
        target=ticket,
        metadata={"transfer_id": str(transfer_id)},
        request=request,
    )
    return transfer
