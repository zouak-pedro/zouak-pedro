from django.conf import settings
from django.db import models

class DoctorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="doctor_profile")
    
    clinic = models.ForeignKey("clinics.Clinic", on_delete=models.PROTECT, related_name="doctors")

    specialty = models.ForeignKey("clinics.Specialty", on_delete=models.PROTECT, related_name="doctors")

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (self.user.get_full_name() or self.user.email)


class SecretaryProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="secretary_profile")

    clinic = models.ForeignKey("clinics.Clinic", on_delete=models.PROTECT, related_name="secretaries")

    created_by = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT, related_name="created_secretaries")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.email