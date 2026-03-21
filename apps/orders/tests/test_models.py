import pytest

from apps.orders.models import Order, OrderItem

from .factories import OrderFactory, OrderItemFactory


@pytest.mark.django_db
class TestOrder:
    def test_order_creation(self):
        order = OrderFactory()
        assert order.pk is not None
        assert order.status == Order.Status.PENDING

    def test_reference_auto_generation(self):
        order = OrderFactory()
        assert order.reference.startswith("TT-")
        assert len(order.reference) == 18  # TT-YYYYMMDD-XXXXXX

    def test_expires_at_default(self):
        order = OrderFactory()
        assert order.expires_at is not None

    def test_str_representation(self):
        order = OrderFactory()
        assert order.reference in str(order)

    def test_uuid_primary_key(self):
        import uuid
        order = OrderFactory()
        assert isinstance(order.pk, uuid.UUID)


@pytest.mark.django_db
class TestOrderItem:
    def test_subtotal_calculated(self):
        from decimal import Decimal
        item = OrderItemFactory(quantity=3, unit_price="10.00")
        item.refresh_from_db()
        assert item.subtotal == Decimal("30.00")


@pytest.mark.django_db
class TestOrderReferenceUniqueness:
    def test_reference_format(self):
        import re
        order = OrderFactory()
        assert re.match(r"TT-\d{8}-[A-Z0-9]{6}", order.reference)

    def test_expires_at_is_set(self):
        from django.utils import timezone
        order = OrderFactory()
        assert order.expires_at > timezone.now() - timezone.timedelta(hours=1)


@pytest.mark.django_db
class TestOrderReferenceCollisionLoop:
    """Covers the while loop in Order.save() when reference already exists (line 57)."""

    def test_reference_collision_generates_new_one(self):
        from unittest.mock import patch
        import apps.orders.models as orders_models
        real_gen = orders_models.generate_order_reference
        call_count = [0]

        def fake_gen():
            call_count[0] += 1
            if call_count[0] == 1:
                return "TT-COLLISION-FIRST"
            return real_gen()

        order1 = OrderFactory()
        Order.objects.filter(pk=order1.pk).update(reference="TT-COLLISION-FIRST")

        with patch("apps.orders.models.generate_order_reference", side_effect=fake_gen):
            order2 = OrderFactory()

        assert order2.reference != "TT-COLLISION-FIRST"
        assert call_count[0] >= 2


@pytest.mark.django_db
class TestOrderItemSubtotalRecalc:
    """Covers OrderItem.save() subtotal recalculation (line 74)."""

    def test_subtotal_recalculated_on_update(self):
        from decimal import Decimal
        item = OrderItemFactory(quantity=2, unit_price="15.00")
        item.quantity = 5
        item.save()
        item.refresh_from_db()
        assert item.subtotal == Decimal("75.00")
