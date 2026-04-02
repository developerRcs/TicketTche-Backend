from rest_framework import serializers

from apps.core.utils import sanitize_html
from .models import Event, TicketType


class TicketTypeSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=True)
    quantity_available = serializers.ReadOnlyField()

    class Meta:
        model = TicketType
        fields = [
            "id",
            "name",
            "description",
            "price",
            "quantity",
            "quantity_sold",
            "quantity_available",
            "sale_start",
            "sale_end",
        ]
        read_only_fields = ["id", "quantity_sold", "quantity_available"]


class TicketTypeUpdateSerializer(serializers.Serializer):
    """Writable serializer for ticket types during event update. Accepts optional id for existing types."""
    id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField(min_value=1)
    sale_start = serializers.DateTimeField(required=False, allow_null=True, default=None)
    sale_end = serializers.DateTimeField(required=False, allow_null=True, default=None)

    def to_internal_value(self, data):
        # Convert empty strings to None for datetime fields before validation
        for field in ("sale_start", "sale_end"):
            if data.get(field) == "":
                data = {**data, field: None}
        return super().to_internal_value(data)

    def validate_description(self, value):
        """Sanitize HTML in ticket type description to prevent XSS."""
        return sanitize_html(value) if value else value


class EventSerializer(serializers.ModelSerializer):
    company = serializers.UUIDField(source="company.id", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    ticket_types = TicketTypeSerializer(many=True, read_only=True)
    tickets_sold = serializers.ReadOnlyField()
    distance_km = serializers.SerializerMethodField()

    def get_distance_km(self, obj):
        return getattr(obj, "distance_km", None)

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "description",
            "slug",
            "company",
            "company_name",
            "location",
            "city",
            "latitude",
            "longitude",
            "location_url",
            "start_date",
            "end_date",
            "cover_image",
            "status",
            "is_online",
            "capacity",
            "sales_cutoff_hours",
            "tickets_sold",
            "ticket_types",
            "distance_km",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "tickets_sold", "created_at", "updated_at"]


class EventCreateSerializer(serializers.ModelSerializer):
    ticket_types = TicketTypeSerializer(many=True, required=False)

    class Meta:
        model = Event
        fields = [
            "title",
            "description",
            "company",
            "location",
            "location_url",
            "start_date",
            "end_date",
            "is_online",
            "capacity",
            "sales_cutoff_hours",
            "ticket_types",
        ]

    def validate_description(self, value):
        """Sanitize HTML in event description to prevent XSS attacks."""
        return sanitize_html(value) if value else value


class EventUpdateSerializer(serializers.ModelSerializer):
    """Used for PATCH/PUT on existing events. Supports ticket type sync."""
    ticket_types = TicketTypeUpdateSerializer(many=True, required=False)

    class Meta:
        model = Event
        fields = [
            "title",
            "description",
            "location",
            "location_url",
            "start_date",
            "end_date",
            "is_online",
            "capacity",
            "sales_cutoff_hours",
            "ticket_types",
        ]

    def validate_description(self, value):
        """Sanitize HTML in event description to prevent XSS attacks."""
        return sanitize_html(value) if value else value

    def validate(self, data):
        capacity = data.get("capacity") or (self.instance.capacity if self.instance else None)
        ticket_types = data.get("ticket_types")
        if capacity and ticket_types:
            total = sum(tt.get("quantity", 0) for tt in ticket_types)
            if total > capacity:
                raise serializers.ValidationError({
                    "ticket_types": f"Total de ingressos ({total}) excede a capacidade do evento ({capacity})."
                })
        return data


class EventCoverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["cover_image"]
