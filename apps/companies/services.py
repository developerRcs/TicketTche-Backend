from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.audit.services import log_action

from .models import Company, CompanyMember

User = get_user_model()


def create_company(name, owner, description="", logo=None, responsible_cpf=None, responsible_cnpj=None, request=None):
    company = Company.objects.create(
        name=name,
        owner=owner,
        description=description,
        logo=logo,
        responsible_cpf=responsible_cpf,
        responsible_cnpj=responsible_cnpj,
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
    from rest_framework import serializers

    if role == CompanyMember.Role.OWNER:
        raise serializers.ValidationError({"role": "Não é possível convidar como proprietário."})
    if (
        role == CompanyMember.Role.ADMIN
        and invited_by is not None
        and getattr(invited_by, "role", "") not in ("admin", "super_admin")
        and not CompanyMember.objects.filter(
            user=invited_by, company=company, role=CompanyMember.Role.OWNER
        ).exists()
    ):
        raise serializers.ValidationError(
            {"role": "Apenas o proprietário pode convidar administradores."}
        )
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


def _require_can_manage_role(company, actor, target_member, new_role=None):
    """Owner memberships are immutable here, and only the owner (or a platform
    admin) can grant/revoke the admin role. Company admins manage staff only."""
    from rest_framework import serializers

    if target_member.role == CompanyMember.Role.OWNER:
        raise serializers.ValidationError(
            {"member": "O proprietário da empresa não pode ser alterado ou removido."}
        )

    if actor is None or getattr(actor, "role", "") in ("admin", "super_admin"):
        return

    actor_is_owner = CompanyMember.objects.filter(
        user=actor, company=company, role=CompanyMember.Role.OWNER
    ).exists()
    touches_admin = (
        target_member.role == CompanyMember.Role.ADMIN
        or new_role == CompanyMember.Role.ADMIN
    )
    if touches_admin and not actor_is_owner:
        raise serializers.ValidationError(
            {"role": "Apenas o proprietário pode gerenciar administradores."}
        )


def update_member_role(member, role, updated_by=None, request=None):
    _require_can_manage_role(member.company, updated_by, member, new_role=role)
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
    _require_can_manage_role(member.company, removed_by, member)
    log_action(
        action="company_member_remove",
        actor=removed_by,
        target=member.company,
        metadata={"member_email": member.user.email},
        request=request,
    )
    member.delete()
