from django.db import models
from .profiles import DoctorProfile, SecretaryProfile
from core.models import ClinicOwnedModel

# Create your models here.
class Clinic(models.Model):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    document_header = models.TextField(blank=True) 
    document_footer = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Specialty(models.Model):
    name = models.CharField(max_length=150, unique=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name



