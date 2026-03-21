import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory, AdminUserFactory, SuperAdminFactory
from apps.companies.tests.factories import CompanyFactory, CompanyMemberFactory
from apps.events.tests.factories import EventFactory, TicketTypeFactory
from apps.tickets.tests.factories import TicketFactory
from apps.orders.tests.factories import OrderFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def admin_user(db):
    return AdminUserFactory()


@pytest.fixture
def super_admin(db):
    return SuperAdminFactory()


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def company(db, user):
    from apps.companies.services import create_company
    return create_company(name="Test Company", owner=user)


@pytest.fixture
def event(db, company):
    return EventFactory(company=company)


@pytest.fixture
def ticket_type(db, event):
    return TicketTypeFactory(event=event)


@pytest.fixture
def ticket(db, user, event, ticket_type):
    return TicketFactory(owner=user, event=event, ticket_type=ticket_type)


@pytest.fixture
def order(db, user, event):
    return OrderFactory(buyer=user, event=event)


@pytest.fixture
def rf():
    from django.test import RequestFactory
    return RequestFactory()
