from django.contrib import admin

from .models import Appointment, AppointmentType

# Register your models here.

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "patient",
        "doctor",
        "type",
        "clinic",
        "scheduled_at",
        "status",
        "is_walk_in",
    )

    list_filter = (
        "clinic",
        "status",
        "is_walk_in",
        "doctor",
        "type",
    )

    search_fields = (
        "patient__first_name",
        "patient__last_name",
        "doctor__user__email"
    )

@admin.register(AppointmentType)
class AppointmentTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)