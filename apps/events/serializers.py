from rest_framework import serializers

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


class EventSerializer(serializers.ModelSerializer):
    company = serializers.UUIDField(source="company.id", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    ticket_types = TicketTypeSerializer(many=True, read_only=True)
    tickets_sold = serializers.ReadOnlyField()

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
            "location_url",
            "start_date",
            "end_date",
            "cover_image",
            "status",
            "is_online",
            "capacity",
            "tickets_sold",
            "ticket_types",
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
            "ticket_types",
        ]


class EventCoverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["cover_image"]
