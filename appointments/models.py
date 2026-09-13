from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from core.models import ClinicOwnedModel

# Create your models here.



class AppointmentType(models.Model):
    """
    Global (cross-clinic) reference list, same pattern as records.Medication
    and clinics.Specialty — grows organically as staff type new types,
    autocomplete-suggested, never blocks entry of something new.
    """
    name = models.CharField(max_length=150, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

class Appointment(ClinicOwnedModel):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", _("Scheduled")
        ARRIVED = "arrived", _("Arrived")
        WAITING = "waiting", _("Waiting")
        WITH_DOCTOR = "with_doctor", _("With doctor")
        DONE = "done", _("Done")
        CANCELLED = "cancelled", _("Cancelled")
        NO_SHOW = "no_show", _("No show")

    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="appointments")

    doctor = models.ForeignKey("clinics.DoctorProfile", on_delete=models.PROTECT, related_name="appointments")

    type = models.ForeignKey(
        AppointmentType, on_delete=models.PROTECT, related_name="appointments",
        null=True, blank=True,
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_appointments")

    scheduled_at = models.DateTimeField()

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    is_walk_in = models.BooleanField(default=False)

    class Meta:
        ordering = ["scheduled_at"]

    def __str__(self):
        return f"{self.patient} with {self.doctor} at {self.scheduled_at:%Y-%m-%d %H:%M}"  
    