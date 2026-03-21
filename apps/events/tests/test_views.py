import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.companies.models import CompanyMember
from apps.companies.services import create_company
from apps.companies.tests.factories import CompanyFactory

from .factories import EventFactory, TicketTypeFactory


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
def company(db, user):
    return create_company(name="Test Co", owner=user)


@pytest.fixture
def event(db, company):
    return EventFactory(company=company)


@pytest.mark.django_db
class TestEventList:
    def test_list_events(self, auth_client):
        EventFactory.create_batch(3)
        url = reverse("event_list")
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data

    def test_filter_by_status(self, auth_client):
        EventFactory(status="published")
        EventFactory(status="draft")
        url = reverse("event_list")
        response = auth_client.get(url, {"status": "published"})
        assert response.status_code == status.HTTP_200_OK
        for ev in response.data["results"]:
            assert ev["status"] == "published"

    def test_unauthenticated_cannot_list(self, api_client):
        url = reverse("event_list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestMyEvents:
    def test_my_events(self, auth_client, event, user):
        url = reverse("my_events")
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data


@pytest.mark.django_db
class TestEventCreate:
    def test_create_event(self, auth_client, company):
        from django.utils import timezone
        url = reverse("event_create")
        data = {
            "title": "New Event",
            "description": "Description",
            "company": str(company.pk),
            "location": "City",
            "start_date": (timezone.now() + timezone.timedelta(days=7)).isoformat(),
            "end_date": (timezone.now() + timezone.timedelta(days=8)).isoformat(),
            "capacity": 100,
        }
        response = auth_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "New Event"

    def test_unauthenticated_cannot_create(self, api_client, company):
        from django.utils import timezone
        url = reverse("event_create")
        data = {
            "title": "New Event",
            "description": "Description",
            "company": str(company.pk),
            "location": "City",
            "start_date": (timezone.now() + timezone.timedelta(days=7)).isoformat(),
            "end_date": (timezone.now() + timezone.timedelta(days=8)).isoformat(),
            "capacity": 100,
        }
        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestEventDetail:
    def test_get_event(self, auth_client, event):
        url = reverse("event_detail", kwargs={"pk": event.pk})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == event.title

    def test_update_event_as_organizer(self, auth_client, event):
        url = reverse("event_detail", kwargs={"pk": event.pk})
        response = auth_client.patch(url, {"title": "Updated Title"}, format="json")
        assert response.status_code == status.HTTP_200_OK

    def test_update_event_not_member_forbidden(self, event):
        other = UserFactory()
        client = APIClient()
        client.force_authenticate(user=other)
        url = reverse("event_detail", kwargs={"pk": event.pk})
        response = client.patch(url, {"title": "Hack"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_event_as_organizer(self, auth_client, event):
        url = reverse("event_detail", kwargs={"pk": event.pk})
        response = auth_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
class TestPublishUnpublish:
    def test_publish_event(self, auth_client, event):
        url = reverse("event_publish", kwargs={"pk": event.pk})
        response = auth_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "published"

    def test_unpublish_event(self, auth_client, event):
        event.status = "published"
        event.save()
        url = reverse("event_unpublish", kwargs={"pk": event.pk})
        response = auth_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "draft"

    def test_non_member_cannot_publish(self, event):
        other = UserFactory()
        client = APIClient()
        client.force_authenticate(user=other)
        url = reverse("event_publish", kwargs={"pk": event.pk})
        response = client.post(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestEventCoverUpload:
    def test_upload_cover(self, auth_client, event):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        img = Image.new("RGB", (100, 100), color="blue")
        img_io = BytesIO()
        img.save(img_io, format="PNG")
        img_io.seek(0)
        cover = SimpleUploadedFile("cover.png", img_io.read(), content_type="image/png")
        url = reverse("event_cover", kwargs={"pk": event.pk})
        response = auth_client.patch(url, {"cover_image": cover}, format="multipart")
        assert response.status_code == status.HTTP_200_OK

    def test_non_member_cannot_upload_cover(self, event):
        other = UserFactory()
        client = APIClient()
        client.force_authenticate(user=other)
        url = reverse("event_cover", kwargs={"pk": event.pk})
        response = client.patch(url, {}, format="multipart")
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestEventSearchFilter:
    def test_search_filter(self, auth_client):
        EventFactory(title="SearchableUniqueEvent")
        EventFactory(title="OtherEvent")
        url = reverse("event_list")
        response = auth_client.get(url, {"search": "SearchableUnique"})
        assert response.status_code == status.HTTP_200_OK
        assert any("SearchableUniqueEvent" in e["title"] for e in response.data["results"])


@pytest.mark.django_db
class TestEventCreateWithTicketTypes:
    def test_create_event_with_ticket_types(self, auth_client, company):
        from django.utils import timezone
        url = reverse("event_create")
        data = {
            "title": "Event With Tickets",
            "description": "Description",
            "company": str(company.pk),
            "location": "City",
            "start_date": (timezone.now() + timezone.timedelta(days=7)).isoformat(),
            "end_date": (timezone.now() + timezone.timedelta(days=8)).isoformat(),
            "capacity": 200,
            "ticket_types": [
                {"name": "VIP", "price": "100.00", "quantity": 50},
                {"name": "General", "price": "50.00", "quantity": 150},
            ],
        }
        response = auth_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data["ticket_types"]) == 2
