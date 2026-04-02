from rest_framework import serializers

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    ticket_type = serializers.UUIDField(source="ticket_type.id", read_only=True)
    ticket_type_name = serializers.CharField(source="ticket_type.name", read_only=True)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True)

    class Meta:
        model = OrderItem
        fields = ["id", "ticket_type", "ticket_type_name", "quantity", "unit_price", "subtotal"]


class OrderSerializer(serializers.ModelSerializer):
    event = serializers.UUIDField(source="event.id", read_only=True)
    event_title = serializers.CharField(source="event.title", read_only=True)
    buyer = serializers.UUIDField(source="buyer.id", read_only=True)
    buyer_email = serializers.EmailField(source="buyer.email", read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True)
    platform_fee = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=True)
    grand_total = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True)
    pix_qr_code = serializers.CharField(read_only=True)
    pix_qr_code_base64 = serializers.CharField(read_only=True)
    mp_order_id = serializers.CharField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "reference",
            "event",
            "event_title",
            "buyer",
            "buyer_email",
            "items",
            "total",
            "platform_fee",
            "grand_total",
            "status",
            "payment_status",
            "payment_method",
            "mp_order_id",
            "pix_qr_code",
            "pix_qr_code_base64",
            "paid_at",
            "created_at",
        ]


class CheckoutItemSerializer(serializers.Serializer):
    ticket_type_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)


class CheckoutSerializer(serializers.Serializer):
    event_id = serializers.UUIDField()
    items = CheckoutItemSerializer(many=True)


class ConfirmOrderSerializer(serializers.Serializer):
    payment_ref = serializers.CharField()


class PayOrderSerializer(serializers.Serializer):
    payment_method = serializers.ChoiceField(choices=["pix", "credit_card", "debit_card"])
    payer_cpf = serializers.CharField(max_length=14)
    payer_name = serializers.CharField(max_length=200, required=False, default="")
    card_token = serializers.CharField(required=False, allow_blank=True, default="")
    mp_payment_method_id = serializers.CharField(required=False, allow_blank=True, default="")
    installments = serializers.IntegerField(min_value=1, max_value=12, required=False, default=1)
    issuer_id = serializers.CharField(required=False, allow_blank=True, default="")
