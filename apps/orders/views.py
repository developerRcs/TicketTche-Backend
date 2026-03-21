from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import StandardPagination

from .models import Order
from .serializers import CheckoutSerializer, ConfirmOrderSerializer, OrderSerializer
from .services import confirm_order, create_checkout


class MyOrdersView(generics.ListAPIView):
    serializer_class = OrderSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = Order.objects.filter(buyer=self.request.user).select_related(
            "event", "buyer"
        ).prefetch_related("items__ticket_type").order_by("-created_at")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(buyer=self.request.user).select_related(
            "event", "buyer"
        ).prefetch_related("items__ticket_type")


class CheckoutView(APIView):
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
