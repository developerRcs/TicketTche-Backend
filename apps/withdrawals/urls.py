from django.urls import path

from .views import (
    AdminWithdrawalApproveView,
    AdminWithdrawalListView,
    AdminWithdrawalRejectView,
    AdminWithdrawalResolveView,
    CompanyBalanceView,
    WithdrawalListCreateView,
)

urlpatterns = [
    path("admin/", AdminWithdrawalListView.as_view(), name="withdrawal-admin-list"),
    path("admin/<uuid:withdrawal_id>/approve/", AdminWithdrawalApproveView.as_view(), name="withdrawal-admin-approve"),
    path("admin/<uuid:withdrawal_id>/reject/", AdminWithdrawalRejectView.as_view(), name="withdrawal-admin-reject"),
    path("admin/<uuid:withdrawal_id>/resolve/", AdminWithdrawalResolveView.as_view(), name="withdrawal-admin-resolve"),
    path("balance/<uuid:company_id>/", CompanyBalanceView.as_view(), name="withdrawal-balance"),
    path("<uuid:company_id>/", WithdrawalListCreateView.as_view(), name="withdrawal-list-create"),
]
