from django.urls import path

from .views import CompanyBalanceView, WithdrawalListCreateView

urlpatterns = [
    path("balance/<uuid:company_id>/", CompanyBalanceView.as_view(), name="withdrawal-balance"),
    path("<uuid:company_id>/", WithdrawalListCreateView.as_view(), name="withdrawal-list-create"),
]
