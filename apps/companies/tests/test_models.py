import pytest
from django.db import IntegrityError

from apps.accounts.tests.factories import UserFactory

from .factories import CompanyFactory, CompanyMemberFactory


@pytest.mark.django_db
class TestCompany:
    def test_company_creation(self):
        company = CompanyFactory()
        assert company.pk is not None
        assert company.is_active is True

    def test_slug_auto_generation(self):
        company = CompanyFactory(name="My Test Company")
        assert company.slug == "my-test-company"

    def test_slug_uniqueness_suffix(self):
        CompanyFactory(name="Same Name")
        company2 = CompanyFactory(name="Same Name")
        assert company2.slug == "same-name-1"

    def test_member_count_property(self):
        company = CompanyFactory()
        # owner creates a member automatically if using service, here we test the property
        assert company.member_count == 0
        CompanyMemberFactory(company=company)
        assert company.member_count == 1

    def test_str_representation(self):
        company = CompanyFactory(name="Test Company")
        assert str(company) == "Test Company"

    def test_uuid_primary_key(self):
        import uuid
        company = CompanyFactory()
        assert isinstance(company.pk, uuid.UUID)


@pytest.mark.django_db
class TestCompanyMember:
    def test_unique_together_constraint(self):
        user = UserFactory()
        company = CompanyFactory()
        CompanyMemberFactory(user=user, company=company)
        with pytest.raises(Exception):
            CompanyMemberFactory(user=user, company=company)

    def test_str_representation(self):
        member = CompanyMemberFactory()
        assert member.user.email in str(member)
