from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.audit.services import log_action

from .models import Company, CompanyMember

User = get_user_model()


def create_company(name, owner, description="", logo=None, responsible_cpf=None, request=None):
    company = Company.objects.create(
        name=name,
        owner=owner,
        description=description,
        logo=logo,
        responsible_cpf=responsible_cpf,
    )
    CompanyMember.objects.create(
        user=owner,
        company=company,
        role=CompanyMember.Role.OWNER,
    )

    if owner.role == User.Role.CUSTOMER:
        owner.role = User.Role.ORGANIZER
        owner.save(update_fields=["role"])

    log_action(
        action="company_create",
        actor=owner,
        target=company,
        request=request,
    )
    return company


def invite_member(company, email, role, invited_by=None, request=None):
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        raise serializers.ValidationError({"email": "No user with this email exists."})

    if CompanyMember.objects.filter(user=user, company=company).exists():
        raise serializers.ValidationError({"email": "User is already a member of this company."})

    member = CompanyMember.objects.create(user=user, company=company, role=role)
    log_action(
        action="company_member_invite",
        actor=invited_by,
        target=company,
        metadata={"email": email, "role": role},
        request=request,
    )
    return member


def update_member_role(member, role, updated_by=None, request=None):
    member.role = role
    member.save(update_fields=["role"])
    log_action(
        action="company_member_role_update",
        actor=updated_by,
        target=member.company,
        metadata={"member_email": member.user.email, "new_role": role},
        request=request,
    )
    return member


def remove_member(member, removed_by=None, request=None):
    log_action(
        action="company_member_remove",
        actor=removed_by,
        target=member.company,
        metadata={"member_email": member.user.email},
        request=request,
    )
    member.delete()
