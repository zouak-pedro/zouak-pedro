from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_save
from django.dispatch import receiver

from .context import get_current_user, get_current_clinic
from .services import AuditLogService


def _log_model_change(sender, instance, created, **kwargs):
    actor = get_current_user()
    clinic = get_current_clinic() or getattr(instance, "clinic", None)

    AuditLogService.log(
        actor=actor,
        clinic=clinic,
        action=AuditLogService.Action.CREATE if created else AuditLogService.Action.UPDATE,
        target=instance,
    )

def connect_model_audit_signals():
    """
    Called once from CoreConfig.ready(). Imports are deferred to inside
    this function (not module level) to avoid circular-import issues —
    by the time ready() runs, every app's models are fully loaded.
    """
    from accounts.models import User
    from clinics.models import Clinic
    from clinics.profiles import DoctorProfile, SecretaryProfile
    from patients.models import Patient
    from appointments.models import Appointment
    from records.models import Prescription, DoctorNote, ProcedureReport, LabworkDemand
    from billing.models import Subscription, Invoice, VisitRecord, PlanChangeRequest, PlanChangeCheckout

    tracked_models = (
        User, Clinic, DoctorProfile, SecretaryProfile,
        Patient, Appointment, Prescription, DoctorNote, ProcedureReport, LabworkDemand,
        Subscription, Invoice, VisitRecord, PlanChangeRequest, PlanChangeCheckout,
    )

    for model in tracked_models:
        post_save.connect(_log_model_change, sender=model, dispatch_uid=f"audit_{model.__name__}")


@receiver(user_logged_in)
def _log_login(sender, user, request, **kwargs):
    AuditLogService.log(
        actor=user,
        clinic=getattr(user, "clinic", None),
        action=AuditLogService.Action.LOGIN,
        path=request.path,
        ip_address=AuditLogService._get_ip(request),
    )


@receiver(user_logged_out)
def _log_logout(sender, user, request, **kwargs):
    if user is None:
        return

    AuditLogService.log(
        actor=user,
        clinic=getattr(user, "clinic", None),
        action=AuditLogService.Action.LOGOUT,
        path=request.path,
        ip_address=AuditLogService._get_ip(request),
    )


@receiver(user_login_failed)
def _log_login_failed(sender, credentials, request=None, **kwargs):
    attempted_email = credentials.get("email", credentials.get("username", ""))

    AuditLogService.log(
        actor=None,
        clinic=None,
        action=AuditLogService.Action.LOGIN_FAILED,
        object_repr=attempted_email,
        path=request.path if request else "",
        ip_address=AuditLogService._get_ip(request) if request else None,
    )


