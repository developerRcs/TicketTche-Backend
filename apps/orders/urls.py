from django.urls import path

from .views import (
    CheckoutView,
    ConfirmOrderView,
    MPWebhookView,
    MyOrdersView,
    OrderDetailView,
    OrderPayStatusView,
    OrderPayView,
)

urlpatterns = [
    path("my/", MyOrdersView.as_view(), name="my_orders"),
    path("webhook/", MPWebhookView.as_view(), name="mp_webhook"),
    path("<uuid:pk>/", OrderDetailView.as_view(), name="order_detail"),
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("<uuid:pk>/confirm/", ConfirmOrderView.as_view(), name="confirm_order"),
    path("<uuid:pk>/pay/", OrderPayView.as_view(), name="order_pay"),
    path("<uuid:pk>/pay/status/", OrderPayStatusView.as_view(), name="order_pay_status"),
]
