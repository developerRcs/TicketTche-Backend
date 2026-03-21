from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.audit.services import log_action
from apps.events.models import Event, TicketType
from apps.tickets.models import Ticket

from .models import Order, OrderItem


def create_checkout(event_id, items, buyer, request=None):
    try:
        event = Event.objects.get(pk=event_id)
    except Event.DoesNotExist:
        raise serializers.ValidationError({"event_id": "Event not found."})

    if event.status != Event.Status.PUBLISHED:
        raise serializers.ValidationError({"event_id": "Event is not available for purchase."})

    now = timezone.now()
    total = Decimal("0.00")
    validated_items = []

    with transaction.atomic():
        for item in items:
            try:
                ticket_type = TicketType.objects.select_for_update().get(
                    pk=item["ticket_type_id"], event=event
                )
            except TicketType.DoesNotExist:
                raise serializers.ValidationError(
                    {"items": f"Ticket type {item['ticket_type_id']} not found for this event."}
                )

            if ticket_type.sale_start and now < ticket_type.sale_start:
                raise serializers.ValidationError(
                    {"items": f"Ticket type {ticket_type.name} is not yet on sale."}
                )
            if ticket_type.sale_end and now > ticket_type.sale_end:
                raise serializers.ValidationError(
                    {"items": f"Ticket type {ticket_type.name} sale has ended."}
                )

            qty = item["quantity"]
            if ticket_type.quantity_available < qty:
                raise serializers.ValidationError(
                    {"items": f"Insufficient tickets available for {ticket_type.name}."}
                )

            ticket_type.quantity_sold += qty
            ticket_type.save(update_fields=["quantity_sold"])

            subtotal = ticket_type.price * qty
            total += subtotal
            validated_items.append(
                {"ticket_type": ticket_type, "quantity": qty, "unit_price": ticket_type.price, "subtotal": subtotal}
            )

        order = Order.objects.create(
            event=event,
            buyer=buyer,
            total=total,
        )

        tickets_to_create = []
        for item_data in validated_items:
            OrderItem.objects.create(
                order=order,
                ticket_type=item_data["ticket_type"],
                quantity=item_data["quantity"],
                unit_price=item_data["unit_price"],
                subtotal=item_data["subtotal"],
            )
            for _ in range(item_data["quantity"]):
                ticket = Ticket(
                    event=event,
                    ticket_type=item_data["ticket_type"],
                    owner=buyer,
                )
                tickets_to_create.append(ticket)

        for ticket in tickets_to_create:
            ticket.save()

        log_action(
            action="order_create",
            actor=buyer,
            target=order,
            metadata={"total": str(total), "event": str(event.id)},
            request=request,
        )

    return {
        "order_id": str(order.id),
        "payment_url": f"/api/v1/orders/{order.id}/confirm/",
        "total": str(total),
        "expires_at": order.expires_at.isoformat(),
    }


def confirm_order(order_id, payment_ref, buyer, request=None):
    try:
        order = Order.objects.get(pk=order_id, buyer=buyer)
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

    log_action(
        action="order_confirm",
        actor=buyer,
        target=order,
        metadata={"payment_ref": payment_ref},
        request=request,
    )

    return order


def cancel_expired_orders():
    from django.db.models import F

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
                # Already processed by another worker
                continue

            for item in order.items.select_related("ticket_type").all():
                TicketType.objects.filter(pk=item.ticket_type_id).update(
                    quantity_sold=F("quantity_sold") - item.quantity
                )
                # Also cancel the tickets belonging to this order
                from apps.tickets.models import Ticket

                Ticket.objects.filter(
                    ticket_type=item.ticket_type,
                    owner=order.buyer,
                    status=Ticket.Status.ACTIVE,
                    created_at__gte=order.created_at,
                ).update(status=Ticket.Status.CANCELLED)

            order.status = Order.Status.CANCELLED
            order.save(update_fields=["status"])
            count += 1

    return count
