from django.contrib import admin

from .models import Company, CompanyMember


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "owner", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug", "owner__email"]
    readonly_fields = ["id", "slug", "created_at"]


@admin.register(CompanyMember)
class CompanyMemberAdmin(admin.ModelAdmin):
    list_display = ["user", "company", "role", "joined_at"]
    list_filter = ["role"]
    search_fields = ["user__email", "company__name"]
