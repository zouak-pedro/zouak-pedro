from django.db import models
from .managers import ClinicManager

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


# Create your models here.

class ClinicOwnedModel(models.Model):
    clinic = models.ForeignKey("clinics.Clinic", on_delete=models.PROTECT, related_name="%(class)s_set")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = ClinicManager()
    class Meta:
        abstract = True


class AuditLog(models.Model):
    class Action(models.TextChoices):
        LOGIN = "login", "Login"
        LOGIN_FAILED = "login_failed", "Login failed"
        LOGOUT = "logout", "Logout"
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        PRINT = "print", "Print"
        VIEW = "view", "View"

    # SET_NULL, not PROTECT/CASCADE — the audit trail must survive the
    # deletion of the clinic or user it references.
    clinic = models.ForeignKey(
        "clinics.Clinic", null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_logs"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_logs"
    )
    actor_email = models.CharField(max_length=254, blank=True)  # frozen snapshot, survives actor deletion

    action = models.CharField(max_length=20, choices=Action.choices)

    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL)
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    target = GenericForeignKey("content_type", "object_id")
    object_repr = models.CharField(max_length=255, blank=True)  # frozen snapshot, survives target deletion

    path = models.CharField(max_length=500, blank=True)
    method = models.CharField(max_length=10, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_display()} by {self.actor_email or 'anonymous'} at {self.created_at:%Y-%m-%d %H:%M}" #type:ignore