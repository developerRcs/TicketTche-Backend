from rest_framework.permissions import BasePermission

from apps.companies.models import CompanyMember


class IsEventOrganizer(BasePermission):
    def has_object_permission(self, request, view, obj):
        company = obj.company
        return CompanyMember.objects.filter(
            user=request.user,
            company=company,
            role__in=["owner", "admin", "staff"],
        ).exists()

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
