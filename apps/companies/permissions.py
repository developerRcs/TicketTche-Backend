from rest_framework.permissions import BasePermission

from .models import CompanyMember


class IsCompanyOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, "company"):
            company = obj.company
        else:
            company = obj
        return CompanyMember.objects.filter(
            user=request.user,
            company=company,
            role__in=["owner", "admin"],
        ).exists()


class IsCompanyMember(BasePermission):
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, "company"):
            company = obj.company
        else:
            company = obj
        return CompanyMember.objects.filter(
            user=request.user,
            company=company,
        ).exists()
