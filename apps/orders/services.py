import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers

from apps.audit.services import log_action
from apps.events.models import Event, TicketType
from apps.tickets.models import Ticket

from .models import Order, OrderItem

logger = logging.getLogger(__name__)

PLATFORM_FEE_RATE = Decimal("0.08")


def _amount_covers_order(paid_amount, order) -> bool:
    """True if the gateway-reported paid amount covers the order's grand_total.

    Guards against fulfilling an order whose captured amount was tampered with
    or underpaid, even when the gateway reports APPROVED.
    """
    try:
        paid = Decimal(str(paid_amount)).quantize(Decimal("0.01"))
    except (TypeError, ValueError):
        return False
    return paid >= order.grand_total.quantize(Decimal("0.01"))


def create_checkout(event_id, items, buyer, request=None):
    try:
        event = Event.objects.get(pk=event_id)
    except Event.DoesNotExist:
        raise serializers.ValidationError({"event_id": "Evento não encontrado."})

    if event.status != Event.Status.PUBLISHED:
        raise serializers.ValidationError({"event_id": "Evento não está disponível para compra."})

    now = timezone.now()

    if event.sales_cutoff_hours is not None:
        from datetime import timedelta
        sales_end = event.start_date - timedelta(hours=event.sales_cutoff_hours)
        if now > sales_end:
            raise serializers.ValidationError(
                {"event_id": f"As vendas deste evento encerraram {event.sales_cutoff_hours}h antes do início."}
            )
    subtotal = Decimal("0.00")
    validated_items = []

    with transaction.atomic():
        for item in items:
            try:
                ticket_type = TicketType.objects.select_for_update().get(
                    pk=item["ticket_type_id"], event=event
                )
            except TicketType.DoesNotExist:
                raise serializers.ValidationError(
                    {"items": f"Tipo de ingresso {item['ticket_type_id']} não encontrado."}
                )

            if ticket_type.sale_start and now < ticket_type.sale_start:
                raise serializers.ValidationError(
                    {"items": f"Ingresso {ticket_type.name} ainda não está à venda."}
                )
            if ticket_type.sale_end and now > ticket_type.sale_end:
                raise serializers.ValidationError(
                    {"items": f"Venda do ingresso {ticket_type.name} encerrada."}
                )

            qty = item["quantity"]
            if ticket_type.quantity_available < qty:
                raise serializers.ValidationError(
                    {"items": f"Ingressos insuficientes para {ticket_type.name}."}
                )

            ticket_type.quantity_sold += qty
            ticket_type.save(update_fields=["quantity_sold"])

            item_subtotal = ticket_type.price * qty
            subtotal += item_subtotal
            validated_items.append(
                {
                    "ticket_type": ticket_type,
                    "quantity": qty,
                    "unit_price": ticket_type.price,
                    "subtotal": item_subtotal,
                }
            )

        platform_fee = (subtotal * PLATFORM_FEE_RATE).quantize(Decimal("0.01"))
        grand_total = subtotal + platform_fee

        order = Order.objects.create(
            event=event,
            buyer=buyer,
            total=subtotal,
            platform_fee=platform_fee,
            grand_total=grand_total,
        )

        for item_data in validated_items:
            OrderItem.objects.create(
                order=order,
                ticket_type=item_data["ticket_type"],
                quantity=item_data["quantity"],
                unit_price=item_data["unit_price"],
                subtotal=item_data["subtotal"],
            )

        log_action(
            action="order_create",
            actor=buyer,
            target=order,
            metadata={
                "subtotal": str(subtotal),
                "platform_fee": str(platform_fee),
                "grand_total": str(grand_total),
                "event": str(event.id),
            },
            request=request,
        )

    return {
        "order_id": str(order.id),
        "reference": order.reference,
        "subtotal": str(subtotal),
        "platform_fee": str(platform_fee),
        "grand_total": str(grand_total),
        "expires_at": order.expires_at.isoformat(),
    }


def process_payment(order_id, payment_method, buyer, payer_cpf, payer_name="",
                    card_token=None, mp_payment_method_id=None, installments=1,
                    issuer_id=None, request=None):
    """
    Process payment for an existing order via MercadoPago.
    payment_method: "pix" | "credit_card" | "debit_card"
    """
    from apps.payments.gateway import CardData, PaymentMethod, PaymentRequest, PaymentStatus, get_gateway

    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(pk=order_id, buyer=buyer)
        except Order.DoesNotExist:
            raise serializers.ValidationError({"order_id": "Pedido não encontrado."})

        if order.status not in (Order.Status.PENDING, Order.Status.FAILED):
            raise serializers.ValidationError({"order_id": "Este pedido não está aguardando pagamento."})

        if order.expires_at < timezone.now():
            raise serializers.ValidationError({"order_id": "Este pedido expirou."})

        from .emails import MAX_PAYMENT_ATTEMPTS
        if order.payment_attempts >= MAX_PAYMENT_ATTEMPTS:
            raise serializers.ValidationError(
                {"order_id": "Número máximo de tentativas de pagamento atingido. Crie um novo pedido."}
            )

        # If the previous attempt was rejected, re-reserve inventory before retrying
        if order.status == Order.Status.FAILED:
            for item in order.items.select_related("ticket_type").all():
                tt = TicketType.objects.select_for_update().get(pk=item.ticket_type_id)
                if tt.quantity_available < item.quantity:
                    raise serializers.ValidationError({"order_id": f"Ingresso '{tt.name}' sem estoque suficiente para nova tentativa."})
                TicketType.objects.filter(pk=item.ticket_type_id).update(
                    quantity_sold=F("quantity_sold") + item.quantity
                )
            order.status = Order.Status.PENDING
            order.save(update_fields=["status"])

        method_map = {
            "pix": PaymentMethod.PIX,
            "credit_card": PaymentMethod.CREDIT_CARD,
            "debit_card": PaymentMethod.DEBIT_CARD,
        }
        mp_method = method_map.get(payment_method)
        if not mp_method:
            raise serializers.ValidationError({"payment_method": "Meio de pagamento inválido."})

        name_parts = payer_name.strip().split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        card_data = None
        if mp_method in (PaymentMethod.CREDIT_CARD, PaymentMethod.DEBIT_CARD):
            if not card_token:
                raise serializers.ValidationError({"card_token": "Token do cartão é obrigatório."})
            card_data = CardData(
                holder_name="",
                number=card_token,
                expiry_month=0,
                expiry_year=0,
                cvv="",
                installments=installments,
            )

        pay_request = PaymentRequest(
            amount=order.grand_total,
            currency="BRL",
            method=mp_method,
            description=f"TicketTchê — {order.event.title}",
            reference=order.reference,
            payer_email=buyer.email,
            card_data=card_data,
            metadata={
                "payer_first_name": first_name,
                "payer_last_name": last_name,
                "payer_cpf": payer_cpf,
                "mp_payment_method_id": mp_payment_method_id or "",
                "issuer_id": issuer_id or "",
            },
        )

        gateway = get_gateway()

        # A previous Pix attempt may still hold a payable QR. If it was already
        # paid, fulfill it instead of charging again; otherwise cancel it at the
        # gateway so the buyer can't end up paying two QRs for the same order.
        if order.mp_order_id and order.payment_status == Order.PaymentStatus.PROCESSING:
            try:
                previous = gateway.get_payment_status(order.mp_order_id)
            except Exception:
                previous = None
            if previous and previous.status == PaymentStatus.APPROVED:
                if _amount_covers_order(previous.amount, order):
                    order.status = Order.Status.PAID
                    order.payment_status = Order.PaymentStatus.COMPLETED
                    order.paid_at = timezone.now()
                    order.save(update_fields=["status", "payment_status", "paid_at"])
                    _create_tickets_for_order(order)
                    return order, previous
            else:
                try:
                    gateway.cancel_payment(order.mp_order_id)
                except Exception:
                    logger.warning(
                        "Could not cancel previous payment %s for order %s",
                        order.mp_order_id, order.id,
                    )

        # preserve previous payment id for audit (will be overwritten by gateway)
        previous_mp_id = order.mp_payment_id or ""
        order.payment_attempts = (order.payment_attempts or 0) + 1
        response = gateway.create_payment(pay_request)

        order.mp_order_id = response.gateway_id
        order.mp_payment_id = response.raw_response.get("mp_payment_id", "")
        order.payment_method = payment_method

        if response.status == PaymentStatus.APPROVED and not _amount_covers_order(response.amount, order):
            logger.error(
                "process_payment amount mismatch: order=%s grand_total=%s paid=%s — not fulfilling",
                order.id, order.grand_total, response.amount,
            )
            response.status = PaymentStatus.PENDING

        if response.status == PaymentStatus.APPROVED:
            order.status = Order.Status.PAID
            order.payment_status = Order.PaymentStatus.COMPLETED
            order.paid_at = timezone.now()
            order.save(update_fields=[
                "mp_order_id", "mp_payment_id", "payment_method", "payment_attempts",
                "status", "payment_status", "paid_at",
                "pix_qr_code", "pix_qr_code_base64",
            ])
            _create_tickets_for_order(order)
        elif response.status == PaymentStatus.REJECTED:
            order.status = Order.Status.FAILED
            order.payment_status = Order.PaymentStatus.FAILED
            order.save(update_fields=[
                "mp_order_id", "mp_payment_id", "payment_method", "payment_attempts",
                "status", "payment_status", "paid_at",
                "pix_qr_code", "pix_qr_code_base64",
            ])
            _release_inventory(order)
            from .tasks import send_payment_failed_email_task
            send_payment_failed_email_task.delay(str(order.id))
        else:
            # Pending (Pix awaiting scan)
            order.payment_status = Order.PaymentStatus.PROCESSING
            if payment_method == "pix":
                order.pix_qr_code = response.pix_qr_code or ""
                order.pix_qr_code_base64 = response.pix_qr_code_image or ""
            order.save(update_fields=[
                "mp_order_id", "mp_payment_id", "payment_method", "payment_attempts",
                "status", "payment_status", "paid_at",
                "pix_qr_code", "pix_qr_code_base64",
            ])

        log_action(
            action="order_payment_attempt",
            actor=buyer,
            target=order,
            metadata={"method": payment_method, "mp_status": response.status.value},
            request=request,
        )

    return order, response


def _create_tickets_for_order(order):
    """Create Ticket objects for all items in a paid order."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status == Order.Status.PAID and Ticket.objects.filter(order=order).exists():
            return
        for item in order.items.select_related("ticket_type").all():
            for _ in range(item.quantity):
                ticket = Ticket(
                    event=order.event,
                    ticket_type=item.ticket_type,
                    owner=order.buyer,
                    order=order,
                )
                ticket.save()


def _release_inventory(order):
    """Decrement quantity_sold for each item in a failed/cancelled order."""
    for item in order.items.select_related("ticket_type").all():
        TicketType.objects.filter(pk=item.ticket_type_id).update(
            quantity_sold=F("quantity_sold") - item.quantity
        )


def _refund_order(order):
    """Mark a PAID order as refunded: cancel its tickets and free inventory.

    Caller must hold the row lock on the order.
    """
    order.status = Order.Status.REFUNDED
    order.payment_status = Order.PaymentStatus.REFUNDED
    order.save(update_fields=["status", "payment_status"])
    Ticket.objects.filter(order=order).exclude(status=Ticket.Status.USED).update(
        status=Ticket.Status.CANCELLED
    )
    _release_inventory(order)
    log_action(
        action="order_refunded",
        actor=None,
        target=order,
        metadata={"mp_order_id": order.mp_order_id},
    )


def _apply_gateway_status(order_id, response, source: str):
    """Apply a gateway-reported payment status to an order.

    Shared by the webhook handler and Pix polling so both enforce the same
    transitions. Row-locks the order to serialize against the expiry task and
    concurrent notifications. Returns (order, refund_late_payment_id).
    """
    from apps.payments.gateway import PaymentStatus

    refund_payment_id = None

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)

        if response.status == PaymentStatus.APPROVED:
            if order.status == Order.Status.PAID:
                pass  # duplicate notification — nothing to do
            elif order.status != Order.Status.PENDING:
                # Paid after the order was cancelled/failed and its inventory
                # released. Fulfilling would oversell — refund the money instead.
                logger.error(
                    "%s: approved payment for %s order %s — refunding",
                    source, order.status, order.id,
                )
                refund_payment_id = response.gateway_id or order.mp_order_id
            elif not _amount_covers_order(response.amount, order):
                logger.error(
                    "%s amount mismatch: order=%s grand_total=%s paid=%s — refusing to fulfill",
                    source, order.id, order.grand_total, response.amount,
                )
            else:
                order.status = Order.Status.PAID
                order.payment_status = Order.PaymentStatus.COMPLETED
                order.paid_at = timezone.now()
                order.save(update_fields=["status", "payment_status", "paid_at"])
                _create_tickets_for_order(order)

        elif response.status == PaymentStatus.REJECTED and order.status == Order.Status.PENDING:
            order.status = Order.Status.FAILED
            order.payment_status = Order.PaymentStatus.FAILED
            order.save(update_fields=["status", "payment_status"])
            _release_inventory(order)
            from .tasks import send_payment_failed_email_task
            transaction.on_commit(lambda: send_payment_failed_email_task.delay(str(order.id)))

        elif response.status == PaymentStatus.REFUNDED and order.status == Order.Status.PAID:
            _refund_order(order)

    if refund_payment_id:
        from apps.payments.gateway import get_gateway
        try:
            get_gateway().refund_payment(refund_payment_id)
            log_action(
                action="order_late_payment_refunded",
                actor=None,
                target=order,
                metadata={"mp_payment_id": refund_payment_id, "source": source},
            )
        except Exception:
            logger.exception(
                "Failed to auto-refund late payment %s (order %s) — needs manual refund",
                refund_payment_id, order.id,
            )

    return order


def check_payment_status(order_id, buyer):
    """Poll payment status from MP (used for Pix polling)."""
    try:
        order = Order.objects.get(pk=order_id, buyer=buyer)
    except Order.DoesNotExist:
        raise serializers.ValidationError({"order_id": "Pedido não encontrado."})

    if not order.mp_order_id:
        return order

    from apps.payments.gateway import get_gateway
    response = get_gateway().get_payment_status(order.mp_order_id)
    return _apply_gateway_status(order.pk, response, source="payment-status-poll")


def handle_mp_webhook(mp_order_id: str):
    """Process an incoming MP webhook notification."""
    try:
        order = Order.objects.get(mp_order_id=mp_order_id)
    except Order.DoesNotExist:
        logger.warning("Webhook for unknown payment id %s — no matching order", mp_order_id)
        return None

    from apps.payments.gateway import get_gateway
    response = get_gateway().get_payment_status(mp_order_id)
    return _apply_gateway_status(order.pk, response, source="webhook")


def confirm_order(order_id, payment_ref, actor, request=None):
    """Admin-only manual confirmation (e.g. payment settled outside the gateway)."""
    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(pk=order_id)
        except Order.DoesNotExist:
            raise serializers.ValidationError({"order_id": "Order not found."})

        if order.status != Order.Status.PENDING:
            raise serializers.ValidationError({"order_id": "Order is not pending."})

        if order.expires_at < timezone.now():
            raise serializers.ValidationError({"order_id": "Order has expired."})

        order.status = Order.Status.PAID
        order.payment_status = Order.PaymentStatus.COMPLETED
        order.payment_method = "manual"
        order.paid_at = timezone.now()
        order.save(update_fields=["status", "payment_status", "payment_method", "paid_at"])
        _create_tickets_for_order(order)

        log_action(
            action="order_confirm",
            actor=actor,
            target=order,
            metadata={"payment_ref": payment_ref},
            request=request,
        )

    return order


def cancel_expired_orders():
    from apps.events.models import TicketType

    expired_ids = list(
        Order.objects.filter(
            status=Order.Status.PENDING,
            expires_at__lt=timezone.now(),
        ).values_list("id", flat=True)
    )

    count = 0
    for order_id in expired_ids:
        with transaction.atomic():
            try:
                order = Order.objects.select_for_update().get(
                    pk=order_id, status=Order.Status.PENDING
                )
            except Order.DoesNotExist:
                continue

            for item in order.items.select_related("ticket_type").all():
                TicketType.objects.filter(pk=item.ticket_type_id).update(
                    quantity_sold=F("quantity_sold") - item.quantity
                )
            Ticket.objects.filter(order=order, status=Ticket.Status.ACTIVE).update(
                status=Ticket.Status.CANCELLED
            )

            order.status = Order.Status.CANCELLED
            order.save(update_fields=["status"])
            count += 1

    return count
