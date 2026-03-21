from django.contrib import admin

from .models import Event, TicketType


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 0


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["title", "company", "status", "start_date", "end_date", "created_at"]
    list_filter = ["status", "is_online"]
    search_fields = ["title", "company__name", "location"]
    inlines = [TicketTypeInline]


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "event", "price", "quantity", "quantity_sold"]
    search_fields = ["name", "event__title"]
