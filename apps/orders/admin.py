from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["subtotal"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["reference", "event", "buyer", "total", "status", "payment_status", "created_at"]
    list_filter = ["status", "payment_status"]
    search_fields = ["reference", "buyer__email", "event__title"]
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ["order", "ticket_type", "quantity", "unit_price", "subtotal"]
