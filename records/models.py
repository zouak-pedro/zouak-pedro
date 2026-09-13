from django.db import models
from core.models import ClinicOwnedModel
from django.utils.translation import gettext_lazy as _
from django_cryptography.fields import encrypt


# Create your models here.

class DoctorDocumentProfile(models.Model):
    """
    Letterhead info printed on every generated document (prescriptions,
    reports, labwork demands...). Kept separate from clinics.DoctorProfile so that
    model stays about org structure, and this stays about print identity.
    signature/stamp are genuinely files (uploaded once, reused every print)
    - everything else in this app is structured data.
    """
    doctor = models.OneToOneField("clinics.DoctorProfile",
                                  on_delete=models.CASCADE, related_name="document_profile")

    professional_title = models.CharField(max_length=100, blank=True)
    registration_number = models.CharField(max_length=100, blank=True)

    signature = models.ImageField(upload_to="doctors/signatures/", blank=True, null=True)
    stamp = models.ImageField(upload_to="doctors/stamps/", blank=True, null=True)

    def __str__(self):
        return f"Document profile for {self.doctor}"

class Prescription(ClinicOwnedModel):
    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT,related_name="prescriptions")
    doctor = models.ForeignKey("clinics.DoctorProfile", on_delete=models.PROTECT, related_name="prescriptions")

    patient_name_override = encrypt(models.CharField(
        max_length=300, blank=True,
        help_text=_("Optional. Overrides the patient's name on this prescription only. does not change the patient's actual record.")
    ))

    notes = encrypt(models.TextField(blank=True))

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Prescription for {self.patient} — {self.created_at:%Y-%m-%d}"

    @property
    def display_patient_name(self):
        """Name to show on the printed document — the override if set, otherwise the patient's actual name."""
        return self.patient_name_override or str(self.patient)

class PrescriptionItem(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name="items")

    medication_name = encrypt(models.CharField(max_length=200))
    dosage = encrypt(models.CharField(max_length=100, blank=True))
    frequency = encrypt(models.CharField(max_length=100, blank=True))
    duration = encrypt(models.CharField(max_length=100, blank=True))
    instructions = encrypt(models.CharField(max_length=255, blank=True))

    def __str__(self):
        return self.medication_name


class Medication(models.Model):
    """
    Global (cross-clinic) reference list of medication names, built 
    organically as doctors write prescriptions. Powers autocomplete only-
    PrescriptionItem.medication_name stays free text, never a FK, so a
    doctor can always type something new without being blocked by this list.
    """
    name = models.CharField(max_length=200, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class DoctorNote(ClinicOwnedModel):
    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="doctor_notes")
    doctor = models.ForeignKey("clinics.DoctorProfile", on_delete=models.PROTECT, related_name="doctor_notes")

    content = encrypt(models.TextField())

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return  f"Note for {self.patient} — {self.created_at:%Y-%m-%d}"



class ProcedureReport(ClinicOwnedModel):
    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="procedure_reports")
    doctor = models.ForeignKey("clinics.DoctorProfile", on_delete=models.PROTECT, related_name="procedure_reports")

    notes = encrypt(models.TextField(blank=True))

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Procedure report for {self.patient} — {self.created_at:%Y-%m-%d}"


class ProcedureItem(models.Model):
    report = models.ForeignKey(ProcedureReport, on_delete=models.CASCADE, related_name="items")

    procedure_name = encrypt(models.CharField(max_length=200))
    findings = encrypt(models.TextField(blank=True))

    def __str__(self):
        return self.procedure_name


class LabworkDemand(ClinicOwnedModel):
    class Urgency(models.TextChoices):
        ROUTINE = "routine", _("Routine")
        URGENT = "urgent", _("Urgent")

    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="labwork_demands")
    doctor = models.ForeignKey("clinics.DoctorProfile", on_delete=models.PROTECT, related_name="labwork_demands")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Labwork demand for {self.patient} — {self.created_at:%Y-%m-%d}"


class LabworkItem(models.Model):
    demand = models.ForeignKey(LabworkDemand, on_delete=models.CASCADE, related_name="items")

    test_name = encrypt(models.CharField(max_length=200))
    urgency = models.CharField(max_length=20, choices=LabworkDemand.Urgency.choices, default=LabworkDemand.Urgency.ROUTINE)
    clinical_indication = encrypt(models.CharField(max_length=255, blank=True))

    def __str__(self):
        return self.test_name

