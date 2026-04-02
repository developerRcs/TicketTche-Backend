import re

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

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
            "role",
            "is_active",
            "avatar",
            "date_joined",
        ]
        read_only_fields = ["id", "date_joined", "full_name"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    cpf = serializers.CharField(required=True, max_length=14)
    role = serializers.ChoiceField(
        choices=["customer", "organizer"],
        default="customer",
        required=False,
        write_only=True,
    )

    class Meta:
        model = CustomUser
        fields = ["email", "first_name", "last_name", "cpf", "password", "password_confirm", "role"]

    def validate_cpf(self, value):
        cpf = re.sub(r'[^0-9]', '', value)
        if len(cpf) != 11:
            raise serializers.ValidationError("CPF deve ter 11 dígitos.")
        formatted = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        try:
            _validate_cpf(formatted)
        except Exception as e:
            raise serializers.ValidationError(str(e))
        return formatted

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        role = validated_data.pop("role", "customer")
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
            "role",
            "is_active",
            "avatar",
            "date_joined",
        ]
        read_only_fields = ["id", "date_joined", "full_name"]
