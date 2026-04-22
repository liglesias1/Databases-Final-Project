from django.contrib import admin
from .models import Manufacturer, ManufacturerMembership, DemandSnapshot


@admin.register(Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    filter_horizontal = ("breweries",)


@admin.register(ManufacturerMembership)
class ManufacturerMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "manufacturer", "role", "created_at")
    list_filter = ("role",)


@admin.register(DemandSnapshot)
class DemandSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "granularity",
        "period_start",
        "style",
        "country",
        "checkin_count",
        "quantity_total",
        "unique_users",
    )
    list_filter = ("granularity",)
