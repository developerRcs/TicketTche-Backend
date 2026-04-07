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
