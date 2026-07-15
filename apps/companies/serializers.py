import re

from rest_framework import serializers

from apps.accounts.models import CustomUser
from apps.core.validators import validate_cpf as _validate_cpf

from .models import Company, CompanyMember

PIX_KEY_TYPES = ("cpf", "cnpj", "email", "phone", "random")


class CompanySerializer(serializers.ModelSerializer):
    owner = serializers.UUIDField(source="owner.id", read_only=True)
    member_count = serializers.ReadOnlyField()

    # Fields containing financial/PII data — only shown to company managers
    SENSITIVE_FIELDS = ("responsible_cpf", "responsible_cnpj", "pix_key", "pix_key_type")

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
            "responsible_cpf",
            "responsible_cnpj",
            "pix_key",
            "pix_key_type",
        ]
        # PIX key changes must go through CompanyPixKeyView (validated + audited);
        # is_active and responsible documents are not self-service editable.
        read_only_fields = [
            "id", "slug", "created_at", "owner", "member_count",
            "is_active", "responsible_cpf", "responsible_cnpj",
            "pix_key", "pix_key_type",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        is_manager = bool(
            user
            and user.is_authenticated
            and (
                getattr(user, "role", "") in ("admin", "super_admin")
                or CompanyMember.objects.filter(
                    user=user, company=instance,
                    role__in=[CompanyMember.Role.OWNER, CompanyMember.Role.ADMIN],
                ).exists()
            )
        )
        if not is_manager:
            for field in self.SENSITIVE_FIELDS:
                data.pop(field, None)
        return data


class CompanyCreateSerializer(serializers.ModelSerializer):
    responsible_cpf = serializers.CharField(required=False, allow_blank=True, max_length=14, default="")
    responsible_cnpj = serializers.CharField(required=False, allow_blank=True, max_length=18, default="")

    class Meta:
        model = Company
        fields = ["name", "description", "logo", "responsible_cpf", "responsible_cnpj"]

    def validate(self, data):
        cpf = data.get("responsible_cpf", "").strip()
        cnpj = data.get("responsible_cnpj", "").strip()

        if not cpf and not cnpj:
            raise serializers.ValidationError(
                {"responsible_cpf": "Informe o CPF ou CNPJ do responsável."}
            )

        if cpf:
            cpf_digits = re.sub(r'[^0-9]', '', cpf)
            if len(cpf_digits) != 11:
                raise serializers.ValidationError({"responsible_cpf": "CPF deve ter 11 dígitos."})
            formatted = f"{cpf_digits[:3]}.{cpf_digits[3:6]}.{cpf_digits[6:9]}-{cpf_digits[9:]}"
            try:
                _validate_cpf(formatted)
            except Exception as e:
                raise serializers.ValidationError({"responsible_cpf": str(e)})
            data["responsible_cpf"] = formatted

        if cnpj:
            cnpj_digits = re.sub(r'[^0-9]', '', cnpj)
            if len(cnpj_digits) != 14:
                raise serializers.ValidationError({"responsible_cnpj": "CNPJ deve ter 14 dígitos."})
            formatted_cnpj = f"{cnpj_digits[:2]}.{cnpj_digits[2:5]}.{cnpj_digits[5:8]}/{cnpj_digits[8:12]}-{cnpj_digits[12:]}"
            data["responsible_cnpj"] = formatted_cnpj

        return data


class CompanyPixKeySerializer(serializers.Serializer):
    pix_key = serializers.CharField(max_length=255)
    pix_key_type = serializers.ChoiceField(choices=[(k, k) for k in PIX_KEY_TYPES])

    def validate(self, data):
        pix_key = data["pix_key"].strip()
        pix_key_type = data["pix_key_type"]

        if pix_key_type == "cpf":
            digits = re.sub(r'[^0-9]', '', pix_key)
            if len(digits) != 11:
                raise serializers.ValidationError({"pix_key": "CPF inválido para chave PIX."})
        elif pix_key_type == "cnpj":
            digits = re.sub(r'[^0-9]', '', pix_key)
            if len(digits) != 14:
                raise serializers.ValidationError({"pix_key": "CNPJ inválido para chave PIX."})
        elif pix_key_type == "email":
            if "@" not in pix_key or "." not in pix_key:
                raise serializers.ValidationError({"pix_key": "E-mail inválido para chave PIX."})
        elif pix_key_type == "phone":
            digits = re.sub(r'[^0-9+]', '', pix_key)
            if len(digits) < 10:
                raise serializers.ValidationError({"pix_key": "Telefone inválido para chave PIX."})
        elif pix_key_type == "random":
            if len(pix_key) < 10:
                raise serializers.ValidationError({"pix_key": "Chave aleatória inválida."})

        data["pix_key"] = pix_key
        return data



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


# The owner role is never assignable via invite/role-update — ownership is set
# at company creation. Prevents admin self-promotion / owner hijack.
ASSIGNABLE_ROLES = [
    (CompanyMember.Role.ADMIN, "Admin"),
    (CompanyMember.Role.STAFF, "Staff"),
]


class InviteMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=ASSIGNABLE_ROLES)


class UpdateMemberRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=ASSIGNABLE_ROLES)

