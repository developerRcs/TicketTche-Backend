from django.contrib import admin

from .models import Ticket, TicketTransfer


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ["id", "event", "ticket_type", "owner", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["owner__email", "event__title"]


@admin.register(TicketTransfer)
class TicketTransferAdmin(admin.ModelAdmin):
    list_display = ["id", "ticket", "from_user", "to_email", "status", "created_at", "expires_at"]
    list_filter = ["status"]
    search_fields = ["from_user__email", "to_email"]
