from django.conf import settings
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.throttling import CheckoutRateThrottle, PaymentRateThrottle
from apps.accounts.permissions import IsAdminOrSuperAdmin

from apps.core.pagination import StandardPagination

from .models import Order
from .serializers import (
    CheckoutSerializer,
    ConfirmOrderSerializer,
    OrderSerializer,
    PayOrderSerializer,
)
from .services import (
    check_payment_status,
    confirm_order,
    create_checkout,
    handle_mp_webhook,
    process_payment,
)


class MyOrdersView(generics.ListAPIView):
    serializer_class = OrderSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = (
            Order.objects.filter(buyer=self.request.user)
            .select_related("event", "buyer")
            .prefetch_related("items__ticket_type")
            .order_by("-created_at")
        )
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer

    def get_queryset(self):
        return (
            Order.objects.filter(buyer=self.request.user)
            .select_related("event", "buyer")
            .prefetch_related("items__ticket_type")
        )


class CheckoutView(APIView):
    throttle_classes = [CheckoutRateThrottle]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = create_checkout(
            event_id=serializer.validated_data["event_id"],
            items=serializer.validated_data["items"],
            buyer=request.user,
            request=request,
        )
        return Response(result, status=status.HTTP_201_CREATED)


class ConfirmOrderView(APIView):
    # SECURITY FIX (FINDING-004): Only admins can manually confirm orders.
    # Normal users must pay through MercadoPago (process_payment + webhook).
    permission_classes = [permissions.IsAuthenticated, IsAdminOrSuperAdmin]

    def post(self, request, pk):
        serializer = ConfirmOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = confirm_order(
            order_id=pk,
            payment_ref=serializer.validated_data["payment_ref"],
            buyer=request.user,
            request=request,
        )
        return Response(OrderSerializer(order).data)


class OrderPayView(APIView):
    throttle_classes = [PaymentRateThrottle]

    def post(self, request, pk):
        serializer = PayOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        order, _response = process_payment(
            order_id=pk,
            payment_method=d["payment_method"],
            buyer=request.user,
            payer_cpf=d["payer_cpf"],
            payer_name=d.get("payer_name", ""),
            card_token=d.get("card_token", ""),
            mp_payment_method_id=d.get("mp_payment_method_id", ""),
            installments=d.get("installments", 1),
            issuer_id=d.get("issuer_id", ""),
            request=request,
        )
        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)


class OrderPayStatusView(APIView):
    def get(self, request, pk):
        order = check_payment_status(order_id=pk, buyer=request.user)
        return Response(OrderSerializer(order).data)


class MPWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # SECURITY FIX (FINDING-005): Always require webhook secret in production.
        # Fail CLOSED: if secret is not configured, reject ALL webhooks.
        webhook_secret = settings.MP_WEBHOOK_SECRET
        if not webhook_secret:
            return Response(
                {"error": "Webhook signature validation not configured."},
                status=status.HTTP_403_FORBIDDEN,
            )

        import hashlib
        import hmac

        ts = request.headers.get("x-request-id", "")
        signature_header = request.headers.get("x-signature", "")
        # MP signature format: "ts=<timestamp>,v1=<hash>"
        received_hash = ""
        for part in signature_header.split(","):
            if part.strip().startswith("v1="):
                received_hash = part.strip()[3:]

        # SECURITY FIX (FINDING-012): Only accept data ID from body, never from query params
        body_data = request.data.get("data", {})
        mp_order_id = body_data.get("id") if isinstance(body_data, dict) else None

        manifest = f"id:{body_data.get('id', '') if isinstance(body_data, dict) else ''};request-id:{ts};"
        expected = hmac.new(
            webhook_secret.encode(),
            manifest.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, received_hash):
            return Response({"error": "Invalid signature"}, status=status.HTTP_403_FORBIDDEN)

        if mp_order_id:
            handle_mp_webhook(str(mp_order_id))
        return Response({"ok": True})
