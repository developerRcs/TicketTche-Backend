from decimal import Decimal

from rest_framework import serializers

from .models import Withdrawal


class WithdrawalSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=True)
    requested_by_email = serializers.EmailField(source="requested_by.email", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Withdrawal
        fields = [
            "id",
            "company",
            "requested_by",
            "requested_by_email",
            "amount",
            "pix_key",
            "pix_key_type",
            "status",
            "status_display",
            "mp_transfer_id",
            "failure_reason",
            "created_at",
            "updated_at",
            "processed_at",
        ]
        read_only_fields = [
            "id",
            "company",
            "requested_by",
            "status",
            "mp_transfer_id",
            "failure_reason",
            "created_at",
            "updated_at",
            "processed_at",
        ]


class WithdrawalCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("10.00"))
    pix_key = serializers.CharField(max_length=255)
    pix_key_type = serializers.ChoiceField(choices=["cpf", "cnpj", "email", "phone", "random"])

    def validate(self, attrs):
        """SECURITY FIX (FINDING-014): Validate PIX key format to prevent injection and fraud."""
        import re

        pix_key = attrs["pix_key"].strip()
        pix_key_type = attrs["pix_key_type"]

        if pix_key_type == "cpf":
            clean = re.sub(r"[^0-9]", "", pix_key)
            if len(clean) != 11:
                raise serializers.ValidationError({"pix_key": "CPF deve ter 11 dígitos."})
        elif pix_key_type == "cnpj":
            clean = re.sub(r"[^0-9]", "", pix_key)
            if len(clean) != 14:
                raise serializers.ValidationError({"pix_key": "CNPJ deve ter 14 dígitos."})
        elif pix_key_type == "email":
            email_re = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
            if not email_re.match(pix_key):
                raise serializers.ValidationError({"pix_key": "E-mail inválido."})
        elif pix_key_type == "phone":
            clean = re.sub(r"[^0-9+]", "", pix_key)
            if len(clean) < 10 or len(clean) > 14:
                raise serializers.ValidationError(
                    {"pix_key": "Telefone inválido. Use formato +5511999999999."}
                )
        elif pix_key_type == "random":
            uuid_re = re.compile(
                r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                re.IGNORECASE,
            )
            if not uuid_re.match(pix_key):
                raise serializers.ValidationError(
                    {"pix_key": "Chave aleatória deve ser um UUID válido (formato xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)."}
                )

        attrs["pix_key"] = pix_key
        return attrs


class BalanceSerializer(serializers.Serializer):
    available_balance = serializers.DecimalField(
        max_digits=12, decimal_places=2, coerce_to_string=True
    )
    pending_balance = serializers.DecimalField(
        max_digits=12, decimal_places=2, coerce_to_string=True
    )
    total_earned = serializers.DecimalField(
        max_digits=12, decimal_places=2, coerce_to_string=True
    )
    total_withdrawn = serializers.DecimalField(
        max_digits=12, decimal_places=2, coerce_to_string=True
    )
