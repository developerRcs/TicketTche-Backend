import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.tickets.models import Ticket, TicketTransfer

from .factories import TicketFactory, TicketTransferFactory


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
def ticket(db, user):
    return TicketFactory(owner=user)


@pytest.mark.django_db
class TestMyTickets:
    def test_my_tickets(self, auth_client, ticket):
        url = reverse("my_tickets")
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data

    def test_filter_by_status(self, auth_client, user):
        TicketFactory(owner=user, status="active")
        TicketFactory(owner=user, status="used")
        url = reverse("my_tickets")
        response = auth_client.get(url, {"status": "active"})
        assert response.status_code == status.HTTP_200_OK
        for t in response.data["results"]:
            assert t["status"] == "active"

    def test_unauthenticated(self, api_client):
        url = reverse("my_tickets")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestTicketDetail:
    def test_ticket_detail(self, auth_client, ticket):
        url = reverse("ticket_detail", kwargs={"pk": ticket.pk})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_cannot_view_others_ticket(self, ticket):
        other = UserFactory()
        client = APIClient()
        client.force_authenticate(user=other)
        url = reverse("ticket_detail", kwargs={"pk": ticket.pk})
        response = client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestInitiateTransfer:
    def test_initiate_transfer(self, auth_client, ticket, user):
        to_user = UserFactory()
        url = reverse("initiate_transfer")
        data = {"ticket_id": str(ticket.pk), "to_email": to_user.email}
        response = auth_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "pending"

    def test_cannot_transfer_others_ticket(self, auth_client):
        other_ticket = TicketFactory()
        to_user = UserFactory()
        url = reverse("initiate_transfer")
        data = {"ticket_id": str(other_ticket.pk), "to_email": to_user.email}
        response = auth_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_transfer_non_active_ticket(self, auth_client, user):
        ticket = TicketFactory(owner=user, status="used")
        to_user = UserFactory()
        url = reverse("initiate_transfer")
        data = {"ticket_id": str(ticket.pk), "to_email": to_user.email}
        response = auth_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestAcceptTransfer:
    def test_accept_transfer(self, ticket, user):
        to_user = UserFactory()
        transfer = TicketTransferFactory(
            ticket=ticket,
            from_user=user,
            to_email=to_user.email,
            owner_confirmed=True,  # owner must confirm before recipient can accept
        )
        client = APIClient()
        client.force_authenticate(user=to_user)
        url = reverse("accept_transfer", kwargs={"pk": transfer.pk})
        response = client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "accepted"


@pytest.mark.django_db
class TestRejectTransfer:
    def test_reject_transfer(self, ticket, user):
        to_user = UserFactory()
        transfer = TicketTransferFactory(
            ticket=ticket,
            from_user=user,
            to_email=to_user.email,
        )
        client = APIClient()
        client.force_authenticate(user=to_user)
        url = reverse("reject_transfer", kwargs={"pk": transfer.pk})
        response = client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "rejected"


@pytest.mark.django_db
class TestCancelTransfer:
    def test_cancel_transfer(self, auth_client, ticket, user):
        to_user = UserFactory()
        transfer = TicketTransferFactory(
            ticket=ticket,
            from_user=user,
            to_email=to_user.email,
        )
        url = reverse("cancel_transfer", kwargs={"pk": transfer.pk})
        response = auth_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "cancelled"


@pytest.mark.django_db
class TestPendingTransfers:
    def test_pending_transfers(self, user):
        TicketTransferFactory(to_email=user.email, status="pending")
        client = APIClient()
        client.force_authenticate(user=user)
        url = reverse("pending_transfers")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1


@pytest.mark.django_db
class TestTasksViaView:
    """Indirectly test tasks through their functions."""
    pass


@pytest.mark.django_db
class TestTicketPermission:
    def test_non_owner_cannot_view_ticket(self):
        owner = UserFactory()
        ticket = TicketFactory(owner=owner)
        other = UserFactory()
        from apps.tickets.permissions import IsTicketOwner
        from rest_framework.test import APIRequestFactory
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = other
        perm = IsTicketOwner()
        assert perm.has_object_permission(request, None, ticket) is False
