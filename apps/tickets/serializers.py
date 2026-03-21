from rest_framework import serializers

from .models import Ticket, TicketTransfer


class TicketSerializer(serializers.ModelSerializer):
    event = serializers.UUIDField(source="event.id", read_only=True)
    event_title = serializers.CharField(source="event.title", read_only=True)
    event_start_date = serializers.DateTimeField(source="event.start_date", read_only=True)
    event_location = serializers.CharField(source="event.location", read_only=True)
    ticket_type = serializers.UUIDField(source="ticket_type.id", read_only=True)
    ticket_type_name = serializers.CharField(source="ticket_type.name", read_only=True)
    ticket_type_price = serializers.DecimalField(
        source="ticket_type.price", max_digits=10, decimal_places=2, coerce_to_string=True, read_only=True
    )
    owner = serializers.UUIDField(source="owner.id", read_only=True)
    owner_email = serializers.EmailField(source="owner.email", read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "event",
            "event_title",
            "event_start_date",
            "event_location",
            "ticket_type",
            "ticket_type_name",
            "ticket_type_price",
            "owner",
            "owner_email",
            "qr_code",
            "status",
            "checked_in_at",
            "created_at",
        ]


class TicketTransferSerializer(serializers.ModelSerializer):
    ticket = serializers.UUIDField(source="ticket.id", read_only=True)
    from_user = serializers.UUIDField(source="from_user.id", read_only=True)
    from_user_email = serializers.EmailField(source="from_user.email", read_only=True)

    class Meta:
        model = TicketTransfer
        fields = [
            "id",
            "ticket",
            "from_user",
            "from_user_email",
            "to_email",
            "status",
            "created_at",
            "expires_at",
        ]


class InitiateTransferSerializer(serializers.Serializer):
    ticket_id = serializers.UUIDField()
    to_email = serializers.EmailField()
