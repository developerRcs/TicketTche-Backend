import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.companies.models import Company, CompanyMember

from .factories import CompanyFactory, CompanyMemberFactory


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
    from apps.companies.services import create_company
    return create_company(name="Test Company", owner=user)


@pytest.mark.django_db
class TestCompanyListCreate:
    def test_list_companies(self, auth_client):
        CompanyFactory.create_batch(3)
        url = reverse("company_list_create")
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data

    def test_create_company(self, auth_client):
        url = reverse("company_list_create")
        data = {"name": "New Company", "description": "A description"}
        response = auth_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "New Company"

    def test_unauthenticated_cannot_create(self, api_client):
        url = reverse("company_list_create")
        data = {"name": "New Company"}
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestMyCompanies:
    def test_my_companies(self, auth_client, company, user):
        url = reverse("my_companies")
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_my_companies_only_own(self, auth_client, user):
        other_user = UserFactory()
        CompanyFactory(owner=other_user)
        url = reverse("my_companies")
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        results = response.data.get("results", response.data)
        for c in results:
            # user should not see other's companies unless a member
            assert c["owner"] == str(user.pk) or CompanyMember.objects.filter(
                user=user, company_id=c["id"]
            ).exists()


@pytest.mark.django_db
class TestCompanyDetail:
    def test_get_company(self, auth_client, company):
        url = reverse("company_detail", kwargs={"pk": company.pk})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == company.name

    def test_update_company_as_owner(self, auth_client, company):
        url = reverse("company_detail", kwargs={"pk": company.pk})
        response = auth_client.patch(url, {"name": "Updated Name"})
        assert response.status_code == status.HTTP_200_OK

    def test_update_company_not_member_forbidden(self, company):
        other_user = UserFactory()
        client = APIClient()
        client.force_authenticate(user=other_user)
        url = reverse("company_detail", kwargs={"pk": company.pk})
        response = client.patch(url, {"name": "Updated Name"})
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestCompanyMembers:
    def test_list_members(self, auth_client, company):
        url = reverse("company_members", kwargs={"pk": company.pk})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_invite_member(self, auth_client, company, user):
        new_user = UserFactory()
        url = reverse("company_invite", kwargs={"pk": company.pk})
        response = auth_client.post(url, {"email": new_user.email, "role": "staff"})
        assert response.status_code == status.HTTP_201_CREATED

    def test_invite_nonexistent_user(self, auth_client, company):
        url = reverse("company_invite", kwargs={"pk": company.pk})
        response = auth_client.post(url, {"email": "nobody@example.com", "role": "staff"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_non_owner_cannot_invite(self, company):
        other_user = UserFactory()
        client = APIClient()
        client.force_authenticate(user=other_user)
        new_user = UserFactory()
        url = reverse("company_invite", kwargs={"pk": company.pk})
        response = client.post(url, {"email": new_user.email, "role": "staff"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_member_role(self, auth_client, company, user):
        new_user = UserFactory()
        member = CompanyMemberFactory(user=new_user, company=company, role="staff")
        url = reverse("company_member_update", kwargs={"pk": company.pk, "member_id": member.pk})
        response = auth_client.patch(url, {"role": "admin"})
        assert response.status_code == status.HTTP_200_OK

    def test_remove_member(self, auth_client, company, user):
        new_user = UserFactory()
        member = CompanyMemberFactory(user=new_user, company=company, role="staff")
        url = reverse("company_member_update", kwargs={"pk": company.pk, "member_id": member.pk})
        response = auth_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
class TestCompanyPermissions:
    def test_is_company_owner_or_admin_permission(self):
        from apps.companies.permissions import IsCompanyOwnerOrAdmin
        from rest_framework.test import APIRequestFactory
        from apps.companies.services import create_company
        factory = APIRequestFactory()
        owner = UserFactory()
        company = create_company(name="Perm Co", owner=owner)
        request = factory.get("/")
        request.user = owner
        perm = IsCompanyOwnerOrAdmin()
        # Owner has permission
        assert perm.has_object_permission(request, None, company) is True

    def test_is_company_member_permission(self):
        from apps.companies.permissions import IsCompanyMember
        from rest_framework.test import APIRequestFactory
        from apps.companies.services import create_company
        factory = APIRequestFactory()
        owner = UserFactory()
        company = create_company(name="Member Co", owner=owner)
        request = factory.get("/")
        request.user = owner
        perm = IsCompanyMember()
        assert perm.has_object_permission(request, None, company) is True

    def test_non_member_no_permission(self):
        from apps.companies.permissions import IsCompanyOwnerOrAdmin
        from rest_framework.test import APIRequestFactory
        from apps.companies.tests.factories import CompanyFactory
        factory = APIRequestFactory()
        non_member = UserFactory()
        company = CompanyFactory()
        request = factory.get("/")
        request.user = non_member
        perm = IsCompanyOwnerOrAdmin()
        assert perm.has_object_permission(request, None, company) is False

    def test_non_member_member_permission_false(self):
        from apps.companies.permissions import IsCompanyMember
        from rest_framework.test import APIRequestFactory
        from apps.companies.tests.factories import CompanyFactory
        factory = APIRequestFactory()
        non_member = UserFactory()
        company = CompanyFactory()
        request = factory.get("/")
        request.user = non_member
        perm = IsCompanyMember()
        assert perm.has_object_permission(request, None, company) is False


@pytest.mark.django_db
class TestCompanyMemberObjectPermission:
    def test_is_company_owner_or_admin_with_member_object(self):
        """Test permission check on a CompanyMember object (has .company attr)."""
        from apps.companies.permissions import IsCompanyOwnerOrAdmin, IsCompanyMember
        from rest_framework.test import APIRequestFactory
        from apps.companies.services import create_company
        from apps.companies.tests.factories import CompanyMemberFactory
        factory = APIRequestFactory()
        owner = UserFactory()
        company = create_company(name="Obj Perm Co", owner=owner)
        member = CompanyMemberFactory(company=company, role="staff")
        request = factory.get("/")
        request.user = owner
        perm = IsCompanyOwnerOrAdmin()
        # obj has .company attribute (CompanyMember)
        assert perm.has_object_permission(request, None, member) is True

    def test_is_company_member_with_member_object(self):
        """Test IsCompanyMember on a CompanyMember object."""
        from apps.companies.permissions import IsCompanyMember
        from rest_framework.test import APIRequestFactory
        from apps.companies.services import create_company
        from apps.companies.tests.factories import CompanyMemberFactory
        factory = APIRequestFactory()
        owner = UserFactory()
        company = create_company(name="Obj Member Co", owner=owner)
        member = CompanyMemberFactory(company=company, role="staff")
        request = factory.get("/")
        request.user = member.user
        perm = IsCompanyMember()
        # obj has .company attribute (CompanyMember)
        assert perm.has_object_permission(request, None, member) is True
