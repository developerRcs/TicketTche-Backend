from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.events.tests.factories import EventFactory, TicketTypeFactory
from apps.orders.models import Order
from apps.orders.services import _apply_gateway_status
from apps.orders.tests.factories import OrderFactory, OrderItemFactory
from apps.payments.gateway import PaymentMethod, PaymentResponse, PaymentStatus
from apps.tickets.models import Ticket


def _response(status, amount, gateway_id="mp-1"):
    return PaymentResponse(
        gateway_id=gateway_id,
        status=status,
        method=PaymentMethod.PIX,
        amount=Decimal(amount),
        reference="ref",
    )


def _order(status=Order.Status.PENDING, total="100.00"):
    event = EventFactory(status="published")
    tt = TicketTypeFactory(event=event, quantity=10, quantity_sold=1)
    order = OrderFactory(
        event=event,
        status=status,
        total=Decimal(total),
        grand_total=Decimal(total),
        mp_order_id="mp-1",
    )
    OrderItemFactory(order=order, ticket_type=tt, quantity=1, unit_price=Decimal(total))
    return order


@pytest.mark.django_db
class TestApplyGatewayStatus:
    def test_approved_pending_order_is_fulfilled(self):
        order = _order()
        _apply_gateway_status(order.pk, _response(PaymentStatus.APPROVED, "100.00"), "test")
        order.refresh_from_db()
        assert order.status == Order.Status.PAID
        assert Ticket.objects.filter(order=order).count() == 1

    def test_approved_cancelled_order_triggers_refund_not_fulfillment(self):
        order = _order(status=Order.Status.CANCELLED)
        mock_gateway = MagicMock()
        with patch("apps.payments.gateway.get_gateway", return_value=mock_gateway):
            _apply_gateway_status(order.pk, _response(PaymentStatus.APPROVED, "100.00"), "test")
        order.refresh_from_db()
        assert order.status == Order.Status.CANCELLED
        assert Ticket.objects.filter(order=order).count() == 0
        mock_gateway.refund_payment.assert_called_once_with("mp-1")

    def test_underpaid_approved_is_not_fulfilled(self):
        order = _order()
        _apply_gateway_status(order.pk, _response(PaymentStatus.APPROVED, "10.00"), "test")
        order.refresh_from_db()
        assert order.status == Order.Status.PENDING
        assert Ticket.objects.filter(order=order).count() == 0

    def test_refunded_paid_order_cancels_tickets_and_inventory(self):
        order = _order(status=Order.Status.PENDING)
        _apply_gateway_status(order.pk, _response(PaymentStatus.APPROVED, "100.00"), "test")
        order.refresh_from_db()
        tt = order.items.first().ticket_type
        sold_before = type(tt).objects.get(pk=tt.pk).quantity_sold

        _apply_gateway_status(order.pk, _response(PaymentStatus.REFUNDED, "100.00"), "test")
        order.refresh_from_db()
        assert order.status == Order.Status.REFUNDED
        assert not Ticket.objects.filter(order=order, status=Ticket.Status.ACTIVE).exists()
        assert type(tt).objects.get(pk=tt.pk).quantity_sold == sold_before - 1

    def test_duplicate_approved_notification_is_idempotent(self):
        order = _order()
        resp = _response(PaymentStatus.APPROVED, "100.00")
        _apply_gateway_status(order.pk, resp, "test")
        _apply_gateway_status(order.pk, resp, "test")
        assert Ticket.objects.filter(order=order).count() == 1


@pytest.mark.django_db
class TestPaymentAttemptCap:
    def test_attempts_capped(self):
        from rest_framework import serializers as drf
        from apps.orders.services import process_payment

        order = _order()
        Order.objects.filter(pk=order.pk).update(payment_attempts=5)
        with pytest.raises(drf.ValidationError):
            process_payment(
                order_id=order.pk,
                payment_method="pix",
                buyer=order.buyer,
                payer_cpf="52998224725",
            )
