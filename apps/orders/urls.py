from django.urls import path

from .views import CheckoutView, ConfirmOrderView, MyOrdersView, OrderDetailView

urlpatterns = [
    path("my/", MyOrdersView.as_view(), name="my_orders"),
    path("<uuid:pk>/", OrderDetailView.as_view(), name="order_detail"),
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("<uuid:pk>/confirm/", ConfirmOrderView.as_view(), name="confirm_order"),
]
