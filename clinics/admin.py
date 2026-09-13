from django.contrib import admin

from .models import Clinic, Specialty
from .profiles import DoctorProfile, SecretaryProfile

# Register your models here.

@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "phone",   
        "created_at",  
        )

    search_fields = (
        "name",
        "phone",
        
    )

@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "clinic",
        "specialty"
    )

    list_filter = (
        "clinic",
        "specialty",
        
    )

    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",  
    )


@admin.register(SecretaryProfile)
class SecretaryProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "clinic",
        "created_by",
        "created_at",
    )

    list_filter = (
        "clinic",
    )

    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
    )

@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    pass