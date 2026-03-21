import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.companies.services import create_company
from apps.events.models import Event
from apps.events.tests.factories import EventFactory, TicketTypeFactory
from apps.orders.models import Order

from .factories import OrderFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def published_event(db, user):
    company = create_company(name="Test Co", owner=user)
    event = EventFactory(company=company, status="published")
    TicketTypeFactory(event=event, quantity=100, quantity_sold=0, price="50.00")
    return event


@pytest.mark.django_db
class TestMyOrders:
    def test_my_orders(self, auth_client, user):
        OrderFactory(buyer=user)
        url = reverse("my_orders")
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data

    def test_filter_by_status(self, auth_client, user):
        OrderFactory(buyer=user, status="pending")
        OrderFactory(buyer=user, status="paid")
        url = reverse("my_orders")
        response = auth_client.get(url, {"status": "pending"})
        assert response.status_code == status.HTTP_200_OK
        for o in response.data["results"]:
            assert o["status"] == "pending"


@pytest.mark.django_db
class TestCheckout:
    def test_checkout_success(self, auth_client, published_event):
        ticket_type = published_event.ticket_types.first()
        url = reverse("checkout")
        data = {
            "event_id": str(published_event.pk),
            "items": [{"ticket_type_id": str(ticket_type.pk), "quantity": 2}],
        }
        response = auth_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert "order_id" in response.data
        assert "total" in response.data

    def test_checkout_insufficient_quantity(self, auth_client, published_event):
        ticket_type = published_event.ticket_types.first()
        ticket_type.quantity = 1
        ticket_type.quantity_sold = 1
        ticket_type.save()
        url = reverse("checkout")
        data = {
            "event_id": str(published_event.pk),
            "items": [{"ticket_type_id": str(ticket_type.pk), "quantity": 5}],
        }
        response = auth_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_checkout_unpublished_event(self, auth_client, user):
        company = create_company(name="Test Co2", owner=user)
        event = EventFactory(company=company, status="draft")
        ticket_type = TicketTypeFactory(event=event, quantity=100)
        url = reverse("checkout")
        data = {
            "event_id": str(event.pk),
            "items": [{"ticket_type_id": str(ticket_type.pk), "quantity": 1}],
        }
        response = auth_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_checkout_past_sale_end(self, auth_client, published_event):
        ticket_type = published_event.ticket_types.first()
        ticket_type.sale_end = timezone.now() - timezone.timedelta(days=1)
        ticket_type.save()
        url = reverse("checkout")
        data = {
            "event_id": str(published_event.pk),
            "items": [{"ticket_type_id": str(ticket_type.pk), "quantity": 1}],
        }
        response = auth_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestConfirmOrder:
    def test_confirm_order(self, auth_client, user, published_event):
        ticket_type = published_event.ticket_types.first()
        order = OrderFactory(buyer=user, event=published_event, status="pending")
        url = reverse("confirm_order", kwargs={"pk": order.pk})
        response = auth_client.post(url, {"payment_ref": "PAY123"}, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "paid"


@pytest.mark.django_db
class TestOrderPermissions:
    def test_unauthenticated_cannot_list_orders(self, api_client):
        url = reverse("my_orders")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_order_detail_wrong_user(self, user, published_event):
        order = OrderFactory(event=published_event)  # different buyer
        other = UserFactory()
        client = APIClient()
        client.force_authenticate(user=other)
        url = reverse("order_detail", kwargs={"pk": order.pk})
        response = client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND
