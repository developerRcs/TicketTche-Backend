import pytest
from rest_framework import serializers

from apps.accounts.tests.factories import UserFactory
from apps.companies.models import Company, CompanyMember
from apps.companies.services import (
    create_company,
    invite_member,
    remove_member,
    update_member_role,
)

from .factories import CompanyFactory, CompanyMemberFactory


@pytest.mark.django_db
class TestCreateCompany:
    def test_create_company_creates_owner_member(self):
        user = UserFactory()
        company = create_company(name="Test Co", owner=user)
        assert Company.objects.filter(pk=company.pk).exists()
        assert CompanyMember.objects.filter(user=user, company=company, role="owner").exists()

    def test_create_company_auto_slug(self):
        user = UserFactory()
        company = create_company(name="My Great Company", owner=user)
        assert company.slug == "my-great-company"


@pytest.mark.django_db
class TestInviteMember:
    def test_invite_existing_user(self):
        owner = UserFactory()
        company = create_company(name="Test Co", owner=owner)
        new_user = UserFactory()
        member = invite_member(company=company, email=new_user.email, role="staff")
        assert member.user == new_user
        assert member.company == company

    def test_invite_nonexistent_user(self):
        owner = UserFactory()
        company = create_company(name="Test Co", owner=owner)
        with pytest.raises(serializers.ValidationError):
            invite_member(company=company, email="nobody@example.com", role="staff")

    def test_invite_duplicate_member(self):
        owner = UserFactory()
        company = create_company(name="Test Co", owner=owner)
        new_user = UserFactory()
        invite_member(company=company, email=new_user.email, role="staff")
        with pytest.raises(serializers.ValidationError):
            invite_member(company=company, email=new_user.email, role="admin")


@pytest.mark.django_db
class TestUpdateMemberRole:
    def test_update_role(self):
        member = CompanyMemberFactory(role="staff")
        updated = update_member_role(member=member, role="admin")
        updated.refresh_from_db()
        assert updated.role == "admin"


@pytest.mark.django_db
class TestRemoveMember:
    def test_remove_member(self):
        member = CompanyMemberFactory()
        pk = member.pk
        remove_member(member=member)
        assert not CompanyMember.objects.filter(pk=pk).exists()
