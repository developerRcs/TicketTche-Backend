import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.tests.factories import SuperAdminFactory, UserFactory
from apps.audit.models import AuditLog


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return SuperAdminFactory()


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def regular_user(db):
    return UserFactory()


@pytest.fixture
def regular_client(regular_user):
    client = APIClient()
    client.force_authenticate(user=regular_user)
    return client


@pytest.mark.django_db
class TestAdminAuditLogView:
    def test_list_audit_logs(self, admin_client):
        AuditLog.objects.create(action="test_action")
        url = reverse("admin_audit_log")
        response = admin_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data

    def test_filter_by_action(self, admin_client):
        AuditLog.objects.create(action="user_login")
        AuditLog.objects.create(action="user_logout")
        url = reverse("admin_audit_log")
        response = admin_client.get(url, {"action": "user_login"})
        assert response.status_code == status.HTTP_200_OK
        for item in response.data["results"]:
            assert item["action"] == "user_login"

    def test_filter_by_actor(self, admin_client, regular_user):
        AuditLog.objects.create(action="test", actor=regular_user)
        url = reverse("admin_audit_log")
        response = admin_client.get(url, {"actor": regular_user.email})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 1

    def test_non_admin_forbidden(self, regular_client):
        url = reverse("admin_audit_log")
        response = regular_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_forbidden(self, api_client):
        url = reverse("admin_audit_log")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestAdminStatsView:
    def test_stats_admin(self, admin_client):
        url = reverse("admin_stats")
        response = admin_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert "total_companies" in response.data
        assert "total_events" in response.data
        assert "total_users" in response.data
        assert "total_orders" in response.data
        assert "total_revenue" in response.data

    def test_stats_non_admin_forbidden(self, regular_client):
        url = reverse("admin_stats")
        response = regular_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAdminUsersView:
    def test_list_users(self, admin_client):
        UserFactory.create_batch(3)
        url = reverse("admin_users")
        response = admin_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data

    def test_search_users(self, admin_client):
        UserFactory(email="searchme@example.com")
        url = reverse("admin_users")
        response = admin_client.get(url, {"search": "searchme"})
        assert response.status_code == status.HTTP_200_OK
        assert any("searchme" in u["email"] for u in response.data["results"])

    def test_activate_user(self, admin_client, db):
        user = UserFactory(is_active=False)
        url = reverse("admin_user_activate", kwargs={"pk": user.pk})
        response = admin_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.is_active is True

    def test_deactivate_user(self, admin_client, db):
        user = UserFactory(is_active=True)
        url = reverse("admin_user_deactivate", kwargs={"pk": user.pk})
        response = admin_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.is_active is False

    def test_non_admin_cannot_list_users(self, regular_client):
        url = reverse("admin_users")
        response = regular_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAdminCompaniesView:
    def test_list_companies(self, admin_client):
        from apps.companies.tests.factories import CompanyFactory
        CompanyFactory.create_batch(3)
        url = reverse("admin_companies")
        response = admin_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data

    def test_search_companies(self, admin_client):
        from apps.companies.tests.factories import CompanyFactory
        CompanyFactory(name="SearchableCompany")
        url = reverse("admin_companies")
        response = admin_client.get(url, {"search": "Searchable"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 1

    def test_non_admin_forbidden(self, regular_client):
        url = reverse("admin_companies")
        response = regular_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAdminEventsView:
    def test_list_events(self, admin_client):
        from apps.events.tests.factories import EventFactory
        EventFactory.create_batch(2)
        url = reverse("admin_events")
        response = admin_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data

    def test_search_events(self, admin_client):
        from apps.events.tests.factories import EventFactory
        EventFactory(title="SearchableEvent")
        url = reverse("admin_events")
        response = admin_client.get(url, {"search": "Searchable"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 1

    def test_filter_events_by_status(self, admin_client):
        from apps.events.tests.factories import EventFactory
        EventFactory(status="published")
        EventFactory(status="draft")
        url = reverse("admin_events")
        response = admin_client.get(url, {"status": "published"})
        assert response.status_code == status.HTTP_200_OK
        for ev in response.data["results"]:
            assert ev["status"] == "published"

    def test_non_admin_forbidden(self, regular_client):
        url = reverse("admin_events")
        response = regular_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
