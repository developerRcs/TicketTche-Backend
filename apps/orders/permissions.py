from rest_framework.permissions import BasePermission


class IsOrderBuyer(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.buyer == request.user
