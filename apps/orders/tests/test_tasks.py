import pytest
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.companies.services import create_company
from apps.events.tests.factories import EventFactory, TicketTypeFactory
from apps.orders.models import Order
from apps.orders.tests.factories import OrderFactory, OrderItemFactory


@pytest.mark.django_db
class TestCancelExpiredOrdersTask:
    def test_cancel_expired_orders_task(self):
        from apps.orders.tasks import cancel_expired_orders
        user = UserFactory()
        company = create_company(name="Task Co", owner=user)
        event = EventFactory(company=company, status="published")
        order = OrderFactory(
            buyer=user,
            event=event,
            status="pending",
            expires_at=timezone.now() - timezone.timedelta(minutes=5),
        )
        result = cancel_expired_orders()
        assert "Cancelled" in result
        order.refresh_from_db()
        assert order.status == Order.Status.CANCELLED

    def test_no_expired_orders(self):
        from apps.orders.tasks import cancel_expired_orders
        result = cancel_expired_orders()
        assert "0" in result
