from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["action", "actor", "target_type", "target_repr", "ip_address", "created_at"]
    list_filter = ["action", "target_type"]
    search_fields = ["action", "actor__email", "target_repr", "ip_address"]
    readonly_fields = ["id", "created_at"]
