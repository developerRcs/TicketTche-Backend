import re

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.core.validators import validate_cnpj as _validate_cnpj
from apps.core.validators import validate_cpf as _validate_cpf

from .models import CustomUser


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "cpf",
            "cnpj",
            "role",
            "is_active",
            "avatar",
            "date_joined",
        ]
        read_only_fields = ["id", "date_joined", "full_name"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    document_type = serializers.ChoiceField(
        choices=["cpf", "cnpj"],
        default="cpf",
        required=False,
        write_only=True,
    )
    cpf = serializers.CharField(required=False, allow_blank=True, max_length=14, default="")
    cnpj = serializers.CharField(required=False, allow_blank=True, max_length=18, default="")
    role = serializers.ChoiceField(
        choices=["customer", "organizer"],
        default="customer",
        required=False,
        write_only=True,
    )

    class Meta:
        model = CustomUser
        fields = ["email", "first_name", "last_name", "document_type", "cpf", "cnpj", "password", "password_confirm", "role"]

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})

        document_type = attrs.get("document_type", "cpf")

        if document_type == "cpf":
            cpf = re.sub(r'[^0-9]', '', attrs.get("cpf", ""))
            if len(cpf) == 0:
                raise serializers.ValidationError({"cpf": "CPF é obrigatório."})
            if len(cpf) != 11:
                raise serializers.ValidationError({"cpf": "CPF deve ter 11 dígitos."})
            formatted = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
            try:
                _validate_cpf(formatted)
            except Exception as e:
                raise serializers.ValidationError({"cpf": str(e)})
            if CustomUser.objects.filter(cpf=formatted).exists():
                raise serializers.ValidationError({"cpf": "Este CPF já está cadastrado."})
            attrs["cpf"] = formatted
            attrs["cnpj"] = None
        else:  # cnpj
            cnpj = re.sub(r'[^0-9]', '', attrs.get("cnpj", ""))
            if len(cnpj) == 0:
                raise serializers.ValidationError({"cnpj": "CNPJ é obrigatório."})
            if len(cnpj) != 14:
                raise serializers.ValidationError({"cnpj": "CNPJ deve ter 14 dígitos."})
            formatted = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
            try:
                _validate_cnpj(formatted)
            except Exception as e:
                raise serializers.ValidationError({"cnpj": str(e)})
            if CustomUser.objects.filter(cnpj=formatted).exists():
                raise serializers.ValidationError({"cnpj": "Este CNPJ já está cadastrado."})
            attrs["cnpj"] = formatted
            attrs["cpf"] = None

        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        validated_data.pop("document_type", None)
        role = validated_data.pop("role", "customer")
        # Remove empty strings so model doesn't receive blank instead of None
        if not validated_data.get("cpf"):
            validated_data["cpf"] = None
        if not validated_data.get("cnpj"):
            validated_data["cnpj"] = None
        from .services import register_user
        return register_user(role=role, **validated_data)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password": "Passwords do not match."})
        return attrs


class SocialAuthSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=["google", "facebook"])
    token = serializers.CharField()
    role = serializers.ChoiceField(
        choices=["customer", "organizer"],
        default="customer",
        required=False,
    )


class AdminUserSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "cpf",
            "cnpj",
            "role",
            "is_active",
            "avatar",
            "date_joined",
        ]
        read_only_fields = ["id", "date_joined", "full_name"]


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password": "As senhas não conferem."})
        return attrs

