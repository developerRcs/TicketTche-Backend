import pytest
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.tests.factories import UserFactory
from apps.companies.services import create_company
from apps.events.models import Event
from apps.events.tests.factories import EventFactory, TicketTypeFactory
from apps.orders.models import Order
from apps.orders.services import cancel_expired_orders, confirm_order, create_checkout

from .factories import OrderFactory, OrderItemFactory


@pytest.mark.django_db
class TestCreateCheckout:
    def test_checkout_success(self):
        user = UserFactory()
        company = create_company(name="Co", owner=user)
        event = EventFactory(company=company, status="published")
        ticket_type = TicketTypeFactory(event=event, quantity=10, price="25.00")

        result = create_checkout(
            event_id=str(event.pk),
            items=[{"ticket_type_id": ticket_type.pk, "quantity": 2}],
            buyer=user,
        )
        assert "order_id" in result
        assert result["subtotal"] == "50.00"

    def test_checkout_insufficient_stock(self):
        user = UserFactory()
        company = create_company(name="Co", owner=user)
        event = EventFactory(company=company, status="published")
        ticket_type = TicketTypeFactory(event=event, quantity=5, quantity_sold=5)
        with pytest.raises(serializers.ValidationError):
            create_checkout(
                event_id=str(event.pk),
                items=[{"ticket_type_id": ticket_type.pk, "quantity": 1}],
                buyer=user,
            )

    def test_checkout_wrong_event(self):
        user = UserFactory()
        with pytest.raises(serializers.ValidationError):
            create_checkout(
                event_id="00000000-0000-0000-0000-000000000000",
                items=[],
                buyer=user,
            )


@pytest.mark.django_db
class TestConfirmOrder:
    def test_confirm_order(self):
        user = UserFactory()
        company = create_company(name="Co", owner=user)
        event = EventFactory(company=company, status="published")
        order = OrderFactory(buyer=user, event=event, status="pending")
        result = confirm_order(order.pk, "PAY123", user)
        assert result.status == Order.Status.PAID
        assert result.payment_status == Order.PaymentStatus.COMPLETED

    def test_confirm_already_paid(self):
        user = UserFactory()
        company = create_company(name="Co", owner=user)
        event = EventFactory(company=company, status="published")
        order = OrderFactory(buyer=user, event=event, status="paid")
        with pytest.raises(serializers.ValidationError):
            confirm_order(order.pk, "PAY123", user)


@pytest.mark.django_db
class TestCancelExpiredOrders:
    def test_cancel_expired_orders(self):
        user = UserFactory()
        company = create_company(name="Co", owner=user)
        event = EventFactory(company=company, status="published")
        ticket_type = TicketTypeFactory(event=event, quantity=10, quantity_sold=2)
        order = OrderFactory(
            buyer=user,
            event=event,
            status="pending",
            expires_at=timezone.now() - timezone.timedelta(minutes=1),
        )
        OrderItemFactory(order=order, ticket_type=ticket_type, quantity=2)
        count = cancel_expired_orders()
        assert count >= 1
        order.refresh_from_db()
        assert order.status == Order.Status.CANCELLED


@pytest.mark.django_db
class TestCheckoutEdgeCases:
    def test_checkout_ticket_type_not_found(self):
        import uuid
        user = UserFactory()
        company = create_company(name="Co2", owner=user)
        event = EventFactory(company=company, status="published")
        with pytest.raises(serializers.ValidationError):
            create_checkout(
                event_id=str(event.pk),
                items=[{"ticket_type_id": uuid.uuid4(), "quantity": 1}],
                buyer=user,
            )

    def test_checkout_sale_not_started(self):
        user = UserFactory()
        company = create_company(name="Co3", owner=user)
        event = EventFactory(company=company, status="published")
        ticket_type = TicketTypeFactory(
            event=event,
            quantity=10,
            sale_start=timezone.now() + timezone.timedelta(days=1),
        )
        with pytest.raises(serializers.ValidationError):
            create_checkout(
                event_id=str(event.pk),
                items=[{"ticket_type_id": ticket_type.pk, "quantity": 1}],
                buyer=user,
            )


@pytest.mark.django_db
class TestConfirmOrderEdgeCases:
    def test_confirm_order_not_found(self):
        import uuid
        user = UserFactory()
        with pytest.raises(serializers.ValidationError):
            confirm_order(uuid.uuid4(), "PAY123", user)

    def test_confirm_expired_order(self):
        user = UserFactory()
        company = create_company(name="Co4", owner=user)
        event = EventFactory(company=company, status="published")
        order = OrderFactory(
            buyer=user,
            event=event,
            status="pending",
            expires_at=timezone.now() - timezone.timedelta(minutes=1),
        )
        with pytest.raises(serializers.ValidationError):
            confirm_order(order.pk, "PAY123", user)


@pytest.mark.django_db
class TestIsOrderBuyerPermission:
    def test_is_order_buyer_permission(self):
        from apps.orders.permissions import IsOrderBuyer
        from rest_framework.test import APIRequestFactory
        user = UserFactory()
        company = create_company(name="Perm Co", owner=user)
        event = EventFactory(company=company, status="published")
        order = OrderFactory(buyer=user, event=event)
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user
        perm = IsOrderBuyer()
        assert perm.has_object_permission(request, None, order) is True

    def test_is_order_buyer_permission_other_user(self):
        from apps.orders.permissions import IsOrderBuyer
        from rest_framework.test import APIRequestFactory
        user = UserFactory()
        other = UserFactory()
        company = create_company(name="Perm Co2", owner=user)
        event = EventFactory(company=company, status="published")
        order = OrderFactory(buyer=user, event=event)
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = other
        perm = IsOrderBuyer()
        assert perm.has_object_permission(request, None, order) is False


@pytest.mark.django_db
class TestCancelExpiredOrdersRaceCondition:
    """Covers the except Order.DoesNotExist: continue path (lines 152-154)."""

    def test_race_condition_order_already_processed(self):
        from unittest.mock import patch, MagicMock
        from apps.orders.services import cancel_expired_orders
        import datetime

        user = UserFactory()
        company = create_company(name="Race Co", owner=user)
        event = EventFactory(company=company, status="published")
        OrderFactory(
            buyer=user,
            event=event,
            status="pending",
            expires_at=timezone.now() - datetime.timedelta(minutes=5),
        )

        def fake_get(*args, **kwargs):
            from apps.orders.models import Order as O
            raise O.DoesNotExist()

        with patch("apps.orders.services.Order.objects.select_for_update") as mock_sfu:
            mock_qs = MagicMock()
            mock_qs.get.side_effect = fake_get
            mock_sfu.return_value = mock_qs
            count = cancel_expired_orders()

        assert count == 0
