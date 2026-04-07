from django.urls import path

from .views import (
    CompanyDetailView,
    CompanyListCreateView,
    CompanyMembersView,
    CompanyPixKeyView,
    InviteMemberView,
    MyCompaniesView,
    UpdateRemoveMemberView,
)

urlpatterns = [
    path("", CompanyListCreateView.as_view(), name="company_list_create"),
    path("my/", MyCompaniesView.as_view(), name="my_companies"),
    path("<uuid:pk>/", CompanyDetailView.as_view(), name="company_detail"),
    path("<uuid:pk>/pix-key/", CompanyPixKeyView.as_view(), name="company_pix_key"),
    path("<uuid:pk>/members/", CompanyMembersView.as_view(), name="company_members"),
    path("<uuid:pk>/members/invite/", InviteMemberView.as_view(), name="company_invite"),
    path(
        "<uuid:pk>/members/<uuid:member_id>/",
        UpdateRemoveMemberView.as_view(),
        name="company_member_update",
    ),
]
