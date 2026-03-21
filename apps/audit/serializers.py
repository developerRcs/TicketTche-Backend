from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor = serializers.UUIDField(source="actor.id", read_only=True, allow_null=True)
    actor_email = serializers.EmailField(source="actor.email", read_only=True, allow_null=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "action",
            "actor",
            "actor_email",
            "target_type",
            "target_id",
            "target_repr",
            "ip_address",
            "user_agent",
            "metadata",
            "created_at",
        ]
