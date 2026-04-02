from django.urls import path

from .views import (
    AdminAuditLogView,
    AdminCompaniesListView,
    AdminEventsListView,
    AdminStatsView,
    AdminUserActivateView,
    AdminUserDeactivateView,
    AdminUserDetailView,
    AdminUsersListView,
)

urlpatterns = [
    path("stats/", AdminStatsView.as_view(), name="admin_stats"),
    path("users/", AdminUsersListView.as_view(), name="admin_users"),
    path("users/<uuid:pk>/", AdminUserDetailView.as_view(), name="admin_user_detail"),
    path("users/<uuid:pk>/activate/", AdminUserActivateView.as_view(), name="admin_user_activate"),
    path(
        "users/<uuid:pk>/deactivate/",
        AdminUserDeactivateView.as_view(),
        name="admin_user_deactivate",
    ),
    path("companies/", AdminCompaniesListView.as_view(), name="admin_companies"),
    path("events/", AdminEventsListView.as_view(), name="admin_events"),
    path("audit-log/", AdminAuditLogView.as_view(), name="admin_audit_log"),
]
