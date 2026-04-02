import re

from rest_framework import serializers

from apps.accounts.models import CustomUser
from apps.core.validators import validate_cpf as _validate_cpf

from .models import Company, CompanyMember


class CompanySerializer(serializers.ModelSerializer):
    owner = serializers.UUIDField(source="owner.id", read_only=True)
    member_count = serializers.ReadOnlyField()

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "slug",
            "logo",
            "description",
            "is_active",
            "created_at",
            "owner",
            "member_count",
        ]
        read_only_fields = ["id", "slug", "created_at", "owner", "member_count"]


class CompanyCreateSerializer(serializers.ModelSerializer):
    responsible_cpf = serializers.CharField(required=True, max_length=14)

    class Meta:
        model = Company
        fields = ["name", "description", "logo", "responsible_cpf"]

    def validate_responsible_cpf(self, value):
        cpf = re.sub(r'[^0-9]', '', value)
        if len(cpf) != 11:
            raise serializers.ValidationError("CPF deve ter 11 dígitos.")
        formatted = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        try:
            _validate_cpf(formatted)
        except Exception as e:
            raise serializers.ValidationError(str(e))
        return formatted


class CompanyMemberSerializer(serializers.ModelSerializer):
    user = serializers.UUIDField(source="user.id", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)
    company = serializers.UUIDField(source="company.id", read_only=True)

    class Meta:
        model = CompanyMember
        fields = [
            "id",
            "user",
            "user_email",
            "user_full_name",
            "company",
            "role",
            "joined_at",
        ]
        read_only_fields = ["id", "user", "user_email", "user_full_name", "company", "joined_at"]


class InviteMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=CompanyMember.Role.choices)


class UpdateMemberRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=CompanyMember.Role.choices)

