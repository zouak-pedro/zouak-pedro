import io
from PIL import Image
from unittest.mock import patch
import datetime as dt
from django.utils import timezone

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from clinics.models import Clinic, Specialty
from clinics.profiles import DoctorProfile
from patients.models import Patient

from .models import (
    Prescription, PrescriptionItem, Medication, DoctorNote,
    ProcedureReport, LabworkDemand, DoctorDocumentProfile,
)
from .services import (
    PrescriptionService, MedicationService, DoctorNoteService,
    ProcedureReportService, LabworkDemandService,
)
from django.db import connection





class PrescriptionServiceTests(TestCase):

    def setUp(self):
        self.clinic_a = Clinic.objects.create(name="Clinic A")
        self.clinic_b = Clinic.objects.create(name="Clinic B")
        self.specialty = Specialty.objects.create(name="General Medicine")

        self.doctor_user_a = User.objects.create_user(email="doc-a@example.com", password="pw", clinic=self.clinic_a) #type:ignore
        self.doctor_a = DoctorProfile.objects.create(user=self.doctor_user_a, clinic=self.clinic_a, specialty=self.specialty)

        self.doctor_user_b = User.objects.create_user(email="doc-b@example.com", password="pw", clinic=self.clinic_b) #type:ignore
        self.doctor_b = DoctorProfile.objects.create(user=self.doctor_user_b, clinic=self.clinic_b, specialty=self.specialty)

        self.patient_a = Patient.objects.create(clinic=self.clinic_a, first_name="John", last_name="A")
        self.patient_b = Patient.objects.create(clinic=self.clinic_b, first_name="Jane", last_name="B")

    def test_create_prescription_with_items(self):
        prescription = PrescriptionService.create_prescription(
            clinic=self.clinic_a, patient=self.patient_a, doctor=self.doctor_a,
            notes="Take with food",
            items=[
                {"medication_name": "Amoxicillin", "dosage": "500mg", "frequency": "3x/day", "duration": "7 days", "instructions": ""},
                {"medication_name": "Paracetamol", "dosage": "1g", "frequency": "as needed", "duration": "", "instructions": "max 4/day"},
            ],
        )

        self.assertEqual(prescription.items.count(), 2) #type:ignore
        self.assertEqual(prescription.notes, "Take with food")
        self.assertEqual(prescription.clinic, self.clinic_a)

    def test_create_prescription_rejects_cross_clinic_patient(self):
        with self.assertRaises(ValueError):
            PrescriptionService.create_prescription(
                clinic=self.clinic_a, patient=self.patient_b, doctor=self.doctor_a, items=[]
            )

    def test_create_prescription_rejects_cross_clinic_doctor(self):
        with self.assertRaises(ValueError):
            PrescriptionService.create_prescription(
                clinic=self.clinic_a, patient=self.patient_a, doctor=self.doctor_b, items=[]
            )

    def test_get_for_patient_only_returns_own_clinic(self):
        PrescriptionService.create_prescription(clinic=self.clinic_a, patient=self.patient_a, doctor=self.doctor_a, items=[])
        PrescriptionService.create_prescription(clinic=self.clinic_b, patient=self.patient_b, doctor=self.doctor_b, items=[])

        results = PrescriptionService.get_for_patient(self.clinic_a, self.patient_a)

        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().clinic, self.clinic_a)

    def test_get_for_patient_filters_by_search(self):
        PrescriptionService.create_prescription(
            clinic=self.clinic_a, patient=self.patient_a, doctor=self.doctor_a,
            items=[{"medication_name": "Amoxicillin", "dosage": "", "frequency": "", "duration": "", "instructions": ""}],
        )
        PrescriptionService.create_prescription(
            clinic=self.clinic_a, patient=self.patient_a, doctor=self.doctor_a,
            items=[{"medication_name": "Ibuprofen", "dosage": "", "frequency": "", "duration": "", "instructions": ""}],
        )

        results = PrescriptionService.get_for_patient(self.clinic_a, self.patient_a, search="amox")

        self.assertEqual(results.count(), 1)

    def test_prescription_uses_patient_name_by_default(self):
        prescription = PrescriptionService.create_prescription(
            clinic=self.clinic_a, patient=self.patient_a, doctor=self.doctor_a, items=[]
        )

        self.assertEqual(prescription.display_patient_name, str(self.patient_a))

    def test_prescription_name_override_does_not_touch_patient_record(self):
        original_name = f"{self.patient_a.first_name} {self.patient_a.last_name}"

        prescription = PrescriptionService.create_prescription(
            clinic=self.clinic_a, patient=self.patient_a, doctor=self.doctor_a, items=[],
            patient_name_override="Jean Dupont",
        )

        self.assertEqual(prescription.display_patient_name, "Jean Dupont")

        self.patient_a.refresh_from_db()
        self.assertEqual(f"{self.patient_a.first_name} {self.patient_a.last_name}", original_name)

    def test_update_prescription_can_change_name_override(self):
        prescription = PrescriptionService.create_prescription(
            clinic=self.clinic_a, patient=self.patient_a, doctor=self.doctor_a, items=[],
        )

        PrescriptionService.update_prescription(
            prescription=prescription, doctor=self.doctor_a, notes="", items=[],
            patient_name_override="Corrected Name",
        )

        prescription.refresh_from_db()
        self.assertEqual(prescription.patient_name_override, "Corrected Name")


class PrescriptionViewTests(TestCase):

    def setUp(self):
        self.clinic_a = Clinic.objects.create(name="Clinic A")
        self.specialty = Specialty.objects.create(name="General Medicine")
        self.user = User.objects.create_user(email="staff-a@example.com", password="StrongPassword123!", clinic=self.clinic_a) #type:ignore
        self.doctor = DoctorProfile.objects.create(user=self.user, clinic=self.clinic_a, specialty=self.specialty)
        self.patient = Patient.objects.create(clinic=self.clinic_a, first_name="John", last_name="A")

    def test_add_prescription_creates_record_and_redirects_to_print(self):
        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        data = {
            "doctor": self.doctor.pk,
            "notes": "",
            "form-TOTAL_FORMS": "3",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-medication_name": "Amoxicillin",
            "form-0-dosage": "500mg",
            "form-0-frequency": "3x/day",
            "form-0-duration": "7 days",
            "form-0-instructions": "",
            "form-1-medication_name": "",
            "form-1-dosage": "",
            "form-1-frequency": "",
            "form-1-duration": "",
            "form-1-instructions": "",
            "form-2-medication_name": "",
            "form-2-dosage": "",
            "form-2-frequency": "",
            "form-2-duration": "",
            "form-2-instructions": "",
        }

        response = self.client.post(reverse("patients:add_prescription", args=[self.patient.pk]), data)

        prescription = Prescription.objects.get(patient=self.patient)

        self.assertRedirects(response, reverse("records:prescription_print", args=[prescription.pk]))
        self.assertEqual(prescription.items.count(), 1) #type:ignore
        self.assertEqual(prescription.items.first().medication_name, "Amoxicillin") #type:ignore

    def test_print_returns_pdf(self):
        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        prescription = PrescriptionService.create_prescription(
            clinic=self.clinic_a, patient=self.patient, doctor=self.doctor,
            items=[{"medication_name": "Amoxicillin", "dosage": "", "frequency": "", "duration": "", "instructions": ""}],
        )

        response = self.client.get(reverse("records:prescription_print", args=[prescription.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_print_rejects_prescription_from_other_clinic(self):
        clinic_b = Clinic.objects.create(name="Clinic B")
        other_user = User.objects.create_user(email="doc-b@example.com", password="pw", clinic=clinic_b) #type:ignore
        other_doctor = DoctorProfile.objects.create(user=other_user, clinic=clinic_b, specialty=self.specialty)
        other_patient = Patient.objects.create(clinic=clinic_b, first_name="Jane", last_name="B")
        other_prescription = PrescriptionService.create_prescription(
            clinic=clinic_b, patient=other_patient, doctor=other_doctor, items=[]
        )

        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        response = self.client.get(reverse("records:prescription_print", args=[other_prescription.pk]))

        self.assertEqual(response.status_code, 404)

    def test_add_prescription_with_name_override(self):
        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        data = {
            "doctor": self.doctor.pk,
            "patient_name_override": "Preferred Name",
            "notes": "",
            "form-TOTAL_FORMS": "3", "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0", "form-MAX_NUM_FORMS": "1000",
            "form-0-medication_name": "", "form-0-dosage": "", "form-0-frequency": "",
            "form-0-duration": "", "form-0-instructions": "",
            "form-1-medication_name": "", "form-1-dosage": "", "form-1-frequency": "",
            "form-1-duration": "", "form-1-instructions": "",
            "form-2-medication_name": "", "form-2-dosage": "", "form-2-frequency": "",
            "form-2-duration": "", "form-2-instructions": "",
        }

        response = self.client.post(reverse("patients:add_prescription", args=[self.patient.pk]), data)

        prescription = Prescription.objects.get(patient=self.patient)
        self.assertRedirects(response, reverse("records:prescription_print", args=[prescription.pk]))
        self.assertEqual(prescription.patient_name_override, "Preferred Name")



class MedicationServiceTests(TestCase):

    def test_register_creates_new_medication(self):
        MedicationService.register("Amoxicillin")
        self.assertTrue(Medication.objects.filter(name="Amoxicillin").exists())

    def test_register_is_case_insensitive_dedup(self):
        MedicationService.register("Amoxicillin")
        MedicationService.register("amoxicillin")
        MedicationService.register("AMOXICILLIN")
        self.assertEqual(Medication.objects.count(), 1)

    def test_register_ignores_blank_name(self):
        MedicationService.register("   ")
        self.assertEqual(Medication.objects.count(), 0)

    def test_suggest_filters_by_query(self):
        Medication.objects.create(name="Amoxicillin")
        Medication.objects.create(name="Paracetamol")
        results = MedicationService.suggest("amox")
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().name, "Amoxicillin") #type:ignore

    def test_suggest_returns_empty_for_blank_query(self):
        Medication.objects.create(name="Amoxicillin")
        results = MedicationService.suggest("")
        self.assertEqual(results.count(), 0)

    def test_create_prescription_registers_medications_globally(self):
        clinic = Clinic.objects.create(name="Clinic A")
        specialty = Specialty.objects.create(name="General Medicine")
        doctor_user = User.objects.create_user(email="d@example.com", password="pw", clinic=clinic) #type:ignore
        doctor = DoctorProfile.objects.create(user=doctor_user, clinic=clinic, specialty=specialty)
        patient = Patient.objects.create(clinic=clinic, first_name="John", last_name="A")

        PrescriptionService.create_prescription(
            clinic=clinic, patient=patient, doctor=doctor,
            items=[{"medication_name": "Ibuprofen", "dosage": "", "frequency": "", "duration": "", "instructions": ""}],
        )

        self.assertTrue(Medication.objects.filter(name="Ibuprofen").exists())


class MedicationSuggestViewTests(TestCase):

    def setUp(self):
        self.clinic = Clinic.objects.create(name="Clinic A")
        self.user = User.objects.create_user(email="staff@example.com", password="StrongPassword123!", clinic=self.clinic) #type:ignore
        Medication.objects.create(name="Amoxicillin")
        Medication.objects.create(name="Paracetamol")

    def test_suggest_requires_login(self):
        response = self.client.get(reverse("records:medication_suggest"), {"q": "amox"})
        self.assertEqual(response.status_code, 302)

    def test_suggest_returns_matching_names(self):
        self.client.login(email="staff@example.com", password="StrongPassword123!")
        response = self.client.get(reverse("records:medication_suggest"), {"q": "amox"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"results": ["Amoxicillin"]})


class DoctorNoteServiceTests(TestCase):

    def setUp(self):
        self.clinic_a = Clinic.objects.create(name="Clinic A")
        self.clinic_b = Clinic.objects.create(name="Clinic B")
        self.specialty = Specialty.objects.create(name="General Medicine")

        self.doctor_user_a = User.objects.create_user(email="doc-a@example.com", password="pw", clinic=self.clinic_a) #type:ignore
        self.doctor_a = DoctorProfile.objects.create(user=self.doctor_user_a, clinic=self.clinic_a, specialty=self.specialty)

        self.doctor_user_b = User.objects.create_user(email="doc-b@example.com", password="pw", clinic=self.clinic_b) #type:ignore
        self.doctor_b = DoctorProfile.objects.create(user=self.doctor_user_b, clinic=self.clinic_b, specialty=self.specialty)

        self.patient_a = Patient.objects.create(clinic=self.clinic_a, first_name="John", last_name="A")
        self.patient_b = Patient.objects.create(clinic=self.clinic_b, first_name="Jane", last_name="B")

    def test_create_note(self):
        note = DoctorNoteService.create_note(
            clinic=self.clinic_a, patient=self.patient_a, doctor=self.doctor_a,
            content="Patient reports mild fever, prescribed rest and fluids.",
        )
        self.assertEqual(note.clinic, self.clinic_a)
        self.assertIn("mild fever", note.content)

    def test_create_note_rejects_cross_clinic_patient(self):
        with self.assertRaises(ValueError):
            DoctorNoteService.create_note(clinic=self.clinic_a, patient=self.patient_b, doctor=self.doctor_a, content="test")

    def test_create_note_rejects_cross_clinic_doctor(self):
        with self.assertRaises(ValueError):
            DoctorNoteService.create_note(clinic=self.clinic_a, patient=self.patient_a, doctor=self.doctor_b, content="test")

    def test_get_for_patient_only_returns_own_clinic(self):
        DoctorNoteService.create_note(clinic=self.clinic_a, patient=self.patient_a, doctor=self.doctor_a, content="A")
        DoctorNoteService.create_note(clinic=self.clinic_b, patient=self.patient_b, doctor=self.doctor_b, content="B")

        results = DoctorNoteService.get_for_patient(self.clinic_a, self.patient_a)

        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().clinic, self.clinic_a)

    def test_get_for_patient_filters_by_search(self):
        DoctorNoteService.create_note(clinic=self.clinic_a, patient=self.patient_a, doctor=self.doctor_a, content="Fever noted")
        DoctorNoteService.create_note(clinic=self.clinic_a, patient=self.patient_a, doctor=self.doctor_a, content="Routine check")

        results = DoctorNoteService.get_for_patient(self.clinic_a, self.patient_a, search="fever")

        self.assertEqual(results.count(), 1)


class DoctorNoteViewTests(TestCase):

    def setUp(self):
        self.clinic_a = Clinic.objects.create(name="Clinic A")
        self.clinic_b = Clinic.objects.create(name="Clinic B")
        self.specialty = Specialty.objects.create(name="General Medicine")

        self.user = User.objects.create_user(email="staff-a@example.com", password="StrongPassword123!", clinic=self.clinic_a) #type:ignore
        self.doctor = DoctorProfile.objects.create(user=self.user, clinic=self.clinic_a, specialty=self.specialty)
        self.patient = Patient.objects.create(clinic=self.clinic_a, first_name="John", last_name="A")

    def test_add_note_creates_record_and_redirects_to_print(self):
        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        response = self.client.post(reverse("patients:add_note", args=[self.patient.pk]), {
            "doctor": self.doctor.pk,
            "content": "Follow-up in 2 weeks.",
        })

        note = DoctorNote.objects.get(patient=self.patient)

        self.assertRedirects(response, reverse("records:note_print", args=[note.pk]))
        self.assertEqual(note.content, "Follow-up in 2 weeks.")

    def test_add_note_requires_content(self):
        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        response = self.client.post(reverse("patients:add_note", args=[self.patient.pk]), {
            "doctor": self.doctor.pk,
            "content": "",
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())

    def test_note_print_returns_pdf(self):
        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        note = DoctorNoteService.create_note(clinic=self.clinic_a, patient=self.patient, doctor=self.doctor, content="Test note.")

        response = self.client.get(reverse("records:note_print", args=[note.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_note_print_rejects_note_from_other_clinic(self):
        other_user = User.objects.create_user(email="doc-b@example.com", password="pw", clinic=self.clinic_b) #type:ignore
        other_doctor = DoctorProfile.objects.create(user=other_user, clinic=self.clinic_b, specialty=self.specialty)
        other_patient = Patient.objects.create(clinic=self.clinic_b, first_name="Jane", last_name="B")
        other_note = DoctorNoteService.create_note(clinic=self.clinic_b, patient=other_patient, doctor=other_doctor, content="Other clinic note.")

        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        response = self.client.get(reverse("records:note_print", args=[other_note.pk]))

        self.assertEqual(response.status_code, 404)


class ProcedureReportServiceTests(TestCase):

    def setUp(self):
        self.clinic_a = Clinic.objects.create(name="Clinic A")
        self.clinic_b = Clinic.objects.create(name="Clinic B")
        self.specialty = Specialty.objects.create(name="General Medicine")
        self.doctor_user_a = User.objects.create_user(email="doc-a@example.com", password="pw", clinic=self.clinic_a) #type:ignore
        self.doctor_a = DoctorProfile.objects.create(user=self.doctor_user_a, clinic=self.clinic_a, specialty=self.specialty)
        self.doctor_user_b = User.objects.create_user(email="doc-b@example.com", password="pw", clinic=self.clinic_b) #type:ignore
        self.doctor_b = DoctorProfile.objects.create(user=self.doctor_user_b, clinic=self.clinic_b, specialty=self.specialty)
        self.patient_a = Patient.objects.create(clinic=self.clinic_a, first_name="John", last_name="A")
        self.patient_b = Patient.objects.create(clinic=self.clinic_b, first_name="Jane", last_name="B")

    def test_create_report_with_items(self):
        report = ProcedureReportService.create_report(
            clinic=self.clinic_a, patient=self.patient_a, doctor=self.doctor_a, notes="Routine check",
            items=[{"procedure_name": "Wound dressing", "findings": "Healing well"}],
        )
        self.assertEqual(report.items.count(), 1) #type:ignore
        self.assertEqual(report.notes, "Routine check")

    def test_create_report_rejects_cross_clinic_patient(self):
        with self.assertRaises(ValueError):
            ProcedureReportService.create_report(clinic=self.clinic_a, patient=self.patient_b, doctor=self.doctor_a, items=[])

    def test_get_for_patient_isolated(self):
        ProcedureReportService.create_report(clinic=self.clinic_a, patient=self.patient_a, doctor=self.doctor_a, items=[])
        ProcedureReportService.create_report(clinic=self.clinic_b, patient=self.patient_b, doctor=self.doctor_b, items=[])

        results = ProcedureReportService.get_for_patient(self.clinic_a, self.patient_a)
        self.assertEqual(results.count(), 1)


class LabworkDemandServiceTests(TestCase):

    def setUp(self):
        self.clinic_a = Clinic.objects.create(name="Clinic A")
        self.clinic_b = Clinic.objects.create(name="Clinic B")
        self.specialty = Specialty.objects.create(name="General Medicine")
        self.doctor_user_a = User.objects.create_user(email="doc-a@example.com", password="pw", clinic=self.clinic_a) #type:ignore
        self.doctor_a = DoctorProfile.objects.create(user=self.doctor_user_a, clinic=self.clinic_a, specialty=self.specialty)
        self.doctor_user_b = User.objects.create_user(email="doc-b@example.com", password="pw", clinic=self.clinic_b) #type:ignore
        self.doctor_b = DoctorProfile.objects.create(user=self.doctor_user_b, clinic=self.clinic_b, specialty=self.specialty)
        self.patient_a = Patient.objects.create(clinic=self.clinic_a, first_name="John", last_name="A")
        self.patient_b = Patient.objects.create(clinic=self.clinic_b, first_name="Jane", last_name="B")

    def test_create_demand_with_items(self):
        demand = LabworkDemandService.create_demand(
            clinic=self.clinic_a, patient=self.patient_a, doctor=self.doctor_a,
            items=[
                {"test_name": "Complete Blood Count", "urgency": LabworkDemand.Urgency.URGENT, "clinical_indication": "Suspected infection"},
                {"test_name": "Lipid Panel", "urgency": LabworkDemand.Urgency.ROUTINE, "clinical_indication": ""},
            ],
        )
        self.assertEqual(demand.items.count(), 2) #type:ignore
        self.assertEqual(demand.items.first().urgency, LabworkDemand.Urgency.URGENT) #type:ignore

    def test_create_demand_rejects_cross_clinic_doctor(self):
        with self.assertRaises(ValueError):
            LabworkDemandService.create_demand(clinic=self.clinic_a, patient=self.patient_a, doctor=self.doctor_b, items=[])

    def test_get_for_patient_isolated(self):
        LabworkDemandService.create_demand(clinic=self.clinic_a, patient=self.patient_a, doctor=self.doctor_a, items=[])
        LabworkDemandService.create_demand(clinic=self.clinic_b, patient=self.patient_b, doctor=self.doctor_b, items=[])

        results = LabworkDemandService.get_for_patient(self.clinic_a, self.patient_a)
        self.assertEqual(results.count(), 1)


class ProcedureAndLabworkViewTests(TestCase):

    def setUp(self):
        self.clinic_a = Clinic.objects.create(name="Clinic A")
        self.specialty = Specialty.objects.create(name="General Medicine")
        self.user = User.objects.create_user(email="staff-a@example.com", password="StrongPassword123!", clinic=self.clinic_a) #type:ignore
        self.doctor = DoctorProfile.objects.create(user=self.user, clinic=self.clinic_a, specialty=self.specialty)
        self.patient = Patient.objects.create(clinic=self.clinic_a, first_name="John", last_name="A")

    def _formset_management(self, prefix, total, initial=0):
        return {
            f"{prefix}-TOTAL_FORMS": str(total),
            f"{prefix}-INITIAL_FORMS": str(initial),
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "1000",
        }

    def test_add_procedure_report_creates_record(self):
        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        data = {
            "doctor": self.doctor.pk,
            "notes": "",
            **self._formset_management("form", 2),
            "form-0-procedure_name": "Suture removal",
            "form-0-findings": "No complications",
            "form-1-procedure_name": "",
            "form-1-findings": "",
        }

        response = self.client.post(reverse("patients:add_procedure_report", args=[self.patient.pk]), data)

        report = ProcedureReport.objects.get(patient=self.patient)
        self.assertRedirects(response, reverse("records:procedure_report_print", args=[report.pk]))
        self.assertEqual(report.items.count(), 1) #type:ignore

    def test_procedure_report_print_returns_pdf(self):
        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        report = ProcedureReportService.create_report(
            clinic=self.clinic_a, patient=self.patient, doctor=self.doctor,
            items=[{"procedure_name": "Suture removal", "findings": ""}],
        )

        response = self.client.get(reverse("records:procedure_report_print", args=[report.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_add_labwork_demand_creates_record(self):
        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        data = {
            "doctor": self.doctor.pk,
            **self._formset_management("form", 2),
            "form-0-test_name": "Complete Blood Count",
            "form-0-urgency": "urgent",
            "form-0-clinical_indication": "Suspected infection",
            "form-1-test_name": "",
            "form-1-urgency": "routine",
            "form-1-clinical_indication": "",
        }

        response = self.client.post(reverse("patients:add_labwork_demand", args=[self.patient.pk]), data)

        demand = LabworkDemand.objects.get(patient=self.patient)
        self.assertRedirects(response, reverse("records:labwork_demand_print", args=[demand.pk]))
        self.assertEqual(demand.items.count(), 1) #type:ignore
        self.assertEqual(demand.items.first().urgency, "urgent") #type:ignore

    def test_labwork_demand_print_returns_pdf(self):
        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        demand = LabworkDemandService.create_demand(
            clinic=self.clinic_a, patient=self.patient, doctor=self.doctor,
            items=[{"test_name": "CBC", "urgency": "routine", "clinical_indication": ""}],
        )

        response = self.client.get(reverse("records:labwork_demand_print", args=[demand.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))


class DocumentProfileViewTests(TestCase):

    def setUp(self): #type:ignore
        self.clinic = Clinic.objects.create(name="Clinic A")
        self.specialty = Specialty.objects.create(name="General Medicine")

        self.doctor_user = User.objects.create_user( #type:ignore
            email="doc@example.com", password="StrongPassword123!",
            clinic=self.clinic, role=User.Role.DOCTOR,
        )
        self.doctor = DoctorProfile.objects.create(
            user=self.doctor_user, clinic=self.clinic, specialty=self.specialty
        )

        self.secretary_user = User.objects.create_user( #type:ignore
            email="sec@example.com", password="StrongPassword123!",
            clinic=self.clinic, role=User.Role.SECRETARY,
        )

    def test_requires_login(self): #type:ignore
        response = self.client.get(reverse("records:edit_document_profile"))
        self.assertEqual(response.status_code, 302)

    def test_secretary_cannot_access(self): #type:ignore
        self.client.login(email="sec@example.com", password="StrongPassword123!")
        response = self.client.get(reverse("records:edit_document_profile"))
        self.assertEqual(response.status_code, 403)

    def test_doctor_gets_auto_created_profile_on_first_visit(self): #type:ignore
        self.client.login(email="doc@example.com", password="StrongPassword123!")
        self.assertFalse(DoctorDocumentProfile.objects.filter(doctor=self.doctor).exists())
        response = self.client.get(reverse("records:edit_document_profile"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(DoctorDocumentProfile.objects.filter(doctor=self.doctor).exists())

    def test_doctor_can_update_title_and_registration(self): #type:ignore
        self.client.login(email="doc@example.com", password="StrongPassword123!")

        response = self.client.post(reverse("records:edit_document_profile"), {
            "professional_title": "General Practitioner",
            "registration_number": "REG-12345",
        })

        self.assertRedirects(response, reverse("records:edit_document_profile"))

        profile = DoctorDocumentProfile.objects.get(doctor=self.doctor)
        self.assertEqual(profile.professional_title, "General Practitioner")
        self.assertEqual(profile.registration_number, "REG-12345")

    def test_doctor_can_upload_signature(self): #type:ignore
        self.client.login(email="doc@example.com", password="StrongPassword123!")

        buffer = io.BytesIO()
        Image.new("RGB", (10, 10), color="white").save(buffer, format="PNG")
        buffer.seek(0)

        fake_image = SimpleUploadedFile("signature.png", buffer.read(), content_type="image/png")

        response = self.client.post(reverse("records:edit_document_profile"), {
            "professional_title": "",
            "registration_number": "",
            "signature": fake_image,
        })

        self.assertRedirects(response, reverse("records:edit_document_profile"))

        profile = DoctorDocumentProfile.objects.get(doctor=self.doctor)
        self.assertTrue(profile.signature)
        self.assertIn("signature", profile.signature.name) #type:ignore

    def setUp(self):
        self.clinic = Clinic.objects.create(name="Clinic A")
        self.specialty = Specialty.objects.create(name="General Medicine")

        self.doctor_user = User.objects.create_user( #type:ignore
            email="doc@example.com", password="StrongPassword123!",
            clinic=self.clinic, role=User.Role.DOCTOR,
        )
        self.doctor = DoctorProfile.objects.create(
            user=self.doctor_user, clinic=self.clinic, specialty=self.specialty
        )

        self.secretary_user = User.objects.create_user( #type:ignore
            email="sec@example.com", password="StrongPassword123!",
            clinic=self.clinic, role=User.Role.SECRETARY,
        )

    def test_requires_login(self):
        response = self.client.get(reverse("records:edit_document_profile"))
        self.assertEqual(response.status_code, 302)

    def test_secretary_cannot_access(self):
        self.client.login(email="sec@example.com", password="StrongPassword123!")

        response = self.client.get(reverse("records:edit_document_profile"))

        self.assertEqual(response.status_code, 403)

    def test_doctor_gets_auto_created_profile_on_first_visit(self):
        self.client.login(email="doc@example.com", password="StrongPassword123!")

        self.assertFalse(DoctorDocumentProfile.objects.filter(doctor=self.doctor).exists())

        response = self.client.get(reverse("records:edit_document_profile"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(DoctorDocumentProfile.objects.filter(doctor=self.doctor).exists())

    def test_doctor_can_update_title_and_registration(self):
        self.client.login(email="doc@example.com", password="StrongPassword123!")

        response = self.client.post(reverse("records:edit_document_profile"), {
            "professional_title": "General Practitioner",
            "registration_number": "REG-12345",
        })

        self.assertRedirects(response, reverse("records:edit_document_profile"))

        profile = DoctorDocumentProfile.objects.get(doctor=self.doctor)
        self.assertEqual(profile.professional_title, "General Practitioner")
        self.assertEqual(profile.registration_number, "REG-12345")

    def test_doctor_can_upload_signature(self):
        self.client.login(email="doc@example.com", password="StrongPassword123!")

        buffer = io.BytesIO()
        Image.new("RGB", (10, 10), color="white").save(buffer, format="PNG")
        buffer.seek(0)

        fake_image = SimpleUploadedFile("signature.png", buffer.read(), content_type="image/png")

        response = self.client.post(reverse("records:edit_document_profile"), {
            "professional_title": "",
            "registration_number": "",
            "signature": fake_image,
        })

        self.assertRedirects(response, reverse("records:edit_document_profile"))

        profile = DoctorDocumentProfile.objects.get(doctor=self.doctor)
        self.assertTrue(profile.signature)
        self.assertIn("signature", profile.signature.name) #type:ignore



class EncryptionAtRestTests(TestCase):

    def setUp(self):
        self.clinic = Clinic.objects.create(name="Clinic A")
        self.specialty = Specialty.objects.create(name="General Medicine")
        self.doctor_user = User.objects.create_user(email="doc@example.com", password="pw", clinic=self.clinic) #type:ignore
        self.doctor = DoctorProfile.objects.create(user=self.doctor_user, clinic=self.clinic, specialty=self.specialty)
        self.patient = Patient.objects.create(clinic=self.clinic, first_name="John", last_name="A")

    def test_doctor_note_content_is_encrypted_at_rest(self):
        secret_content = "Patient has a rare condition XYZ123"

        note = DoctorNoteService.create_note(
            clinic=self.clinic, patient=self.patient, doctor=self.doctor, content=secret_content
        )

        # Bypass the ORM entirely — read the raw column value straight from Postgres
        with connection.cursor() as cursor:
            cursor.execute("SELECT content FROM records_doctornote WHERE id = %s", [note.pk])
            raw_value = cursor.fetchone()[0]

        self.assertNotIn(secret_content, raw_value)
        self.assertNotEqual(raw_value, secret_content)

        # But the ORM should still transparently decrypt it back correctly
        note.refresh_from_db()
        self.assertEqual(note.content, secret_content)

    def test_prescription_item_medication_name_is_encrypted_at_rest(self):
        prescription = PrescriptionService.create_prescription(
            clinic=self.clinic, patient=self.patient, doctor=self.doctor,
            items=[{"medication_name": "SecretDrugName", "dosage": "", "frequency": "", "duration": "", "instructions": ""}],
        )
        item = prescription.items.first() #type:ignore

        with connection.cursor() as cursor:
            cursor.execute("SELECT medication_name FROM records_prescriptionitem WHERE id = %s", [item.pk])
            raw_value = cursor.fetchone()[0]

        self.assertNotIn("SecretDrugName", raw_value)

        item.refresh_from_db()
        self.assertEqual(item.medication_name, "SecretDrugName")

    def test_patient_address_is_encrypted_at_rest(self):
        patient = Patient.objects.create(
            clinic=self.clinic, first_name="Jane", last_name="B", address="123 Secret Street, Algiers"
        )

        with connection.cursor() as cursor:
            cursor.execute("SELECT address FROM patients_patient WHERE id = %s", [patient.pk])
            raw_value = cursor.fetchone()[0]

        self.assertNotIn("Secret Street", raw_value)

        patient.refresh_from_db()
        self.assertEqual(patient.address, "123 Secret Street, Algiers")

    def test_patient_name_is_not_encrypted(self):
        """
        Confirms the scoping decision held: name stays in the clear for
        list/sort performance, per the recommendation this was built against.
        """
        patient = Patient.objects.create(clinic=self.clinic, first_name="Plaintext", last_name="Name")

        with connection.cursor() as cursor:
            cursor.execute("SELECT first_name FROM patients_patient WHERE id = %s", [patient.pk])
            raw_value = cursor.fetchone()[0]

        self.assertEqual(raw_value, "Plaintext")



class PrescriptionEditTests(TestCase):

    def setUp(self):
        self.clinic = Clinic.objects.create(name="Clinic A")
        self.specialty = Specialty.objects.create(name="General Medicine")
        self.user = User.objects.create_user(email="doc@example.com", password="StrongPassword123!", clinic=self.clinic) #type:ignore
        self.doctor = DoctorProfile.objects.create(user=self.user, clinic=self.clinic, specialty=self.specialty)
        self.patient = Patient.objects.create(clinic=self.clinic, first_name="John", last_name="A")

    def test_can_edit_same_day_prescription(self):
        prescription = PrescriptionService.create_prescription(
            clinic=self.clinic, patient=self.patient, doctor=self.doctor,
            items=[{"medication_name": "Amoxicillin", "dosage": "", "frequency": "", "duration": "", "instructions": ""}],
        )

        self.client.login(email="doc@example.com", password="StrongPassword123!")

        data = {
            "doctor": self.doctor.pk, "notes": "Updated notes",
            "form-TOTAL_FORMS": "3", "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0", "form-MAX_NUM_FORMS": "1000",
            "form-0-medication_name": "Ibuprofen", "form-0-dosage": "", "form-0-frequency": "",
            "form-0-duration": "", "form-0-instructions": "",
            "form-1-medication_name": "", "form-1-dosage": "", "form-1-frequency": "",
            "form-1-duration": "", "form-1-instructions": "",
            "form-2-medication_name": "", "form-2-dosage": "", "form-2-frequency": "",
            "form-2-duration": "", "form-2-instructions": "",
        }

        response = self.client.post(
            reverse("patients:edit_prescription", args=[self.patient.pk, prescription.pk]), data
        )

        self.assertRedirects(response, reverse("records:prescription_print", args=[prescription.pk]))

        prescription.refresh_from_db()
        self.assertEqual(prescription.notes, "Updated notes")
        self.assertEqual(prescription.items.count(), 1) #type:ignore
        self.assertEqual(prescription.items.first().medication_name, "Ibuprofen") #type:ignore

    def test_cannot_edit_prescription_from_a_previous_day(self):
        prescription = PrescriptionService.create_prescription(
            clinic=self.clinic, patient=self.patient, doctor=self.doctor, items=[]
        )
        # Simulate it having been created yesterday
        from django.utils import timezone
        from datetime import timedelta
        Prescription.objects.filter(pk=prescription.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        prescription.refresh_from_db()

        self.client.login(email="doc@example.com", password="StrongPassword123!")

        data = {
            "doctor": self.doctor.pk, "notes": "Trying to edit",
            "form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0", "form-MAX_NUM_FORMS": "1000",
            "form-0-medication_name": "", "form-0-dosage": "", "form-0-frequency": "",
            "form-0-duration": "", "form-0-instructions": "",
        }

        response = self.client.post(
            reverse("patients:edit_prescription", args=[self.patient.pk, prescription.pk]), data
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("can only be edited on the day", str(response.context["form"].errors))

        prescription.refresh_from_db()
        self.assertNotEqual(prescription.notes, "Trying to edit")


class NoteEditTests(TestCase):

    def setUp(self):
        self.clinic = Clinic.objects.create(name="Clinic A")
        self.specialty = Specialty.objects.create(name="General Medicine")
        self.user = User.objects.create_user(email="doc@example.com", password="StrongPassword123!", clinic=self.clinic) #type:ignore
        self.doctor = DoctorProfile.objects.create(user=self.user, clinic=self.clinic, specialty=self.specialty)
        self.patient = Patient.objects.create(clinic=self.clinic, first_name="John", last_name="A")

    def test_can_edit_same_day_note(self):
        note = DoctorNoteService.create_note(
            clinic=self.clinic, patient=self.patient, doctor=self.doctor, content="Original content"
        )

        self.client.login(email="doc@example.com", password="StrongPassword123!")

        response = self.client.post(
            reverse("patients:edit_note", args=[self.patient.pk, note.pk]),
            {"doctor": self.doctor.pk, "content": "Corrected content"},
        )

        self.assertRedirects(response, reverse("records:note_print", args=[note.pk]))

        note.refresh_from_db()
        self.assertEqual(note.content, "Corrected content")

    def test_cannot_edit_note_from_a_previous_day(self):
        from django.utils import timezone
        from datetime import timedelta

        note = DoctorNoteService.create_note(
            clinic=self.clinic, patient=self.patient, doctor=self.doctor, content="Original content"
        )
        DoctorNote.objects.filter(pk=note.pk).update(created_at=timezone.now() - timedelta(days=1))
        note.refresh_from_db()

        self.client.login(email="doc@example.com", password="StrongPassword123!")

        response = self.client.post(
            reverse("patients:edit_note", args=[self.patient.pk, note.pk]),
            {"doctor": self.doctor.pk, "content": "Trying to edit"},
        )

        self.assertEqual(response.status_code, 200)

        note.refresh_from_db()
        self.assertEqual(note.content, "Original content")



class SameDayEditTimezoneTests(TestCase):

    def setUp(self):
        self.clinic = Clinic.objects.create(name="Clinic A")
        self.specialty = Specialty.objects.create(name="General Medicine")
        self.user = User.objects.create_user(email="doc@example.com", password="pw", clinic=self.clinic) #type:ignore
        self.doctor = DoctorProfile.objects.create(user=self.user, clinic=self.clinic, specialty=self.specialty)
        self.patient = Patient.objects.create(clinic=self.clinic, first_name="John", last_name="A")

    @patch("django.utils.timezone.now")
    def test_note_created_just_after_utc_midnight_is_still_same_day_in_algiers(self, mock_now):
        fixed_utc_time = dt.datetime(2025, 6, 15, 0, 30, 0, tzinfo=dt.timezone.utc)
        mock_now.return_value = fixed_utc_time

        note = DoctorNoteService.create_note(
            clinic=self.clinic, patient=self.patient, doctor=self.doctor, content="Original"
        )

        DoctorNoteService.update_note(note=note, doctor=self.doctor, content="Edited")

        note.refresh_from_db()
        self.assertEqual(note.content, "Edited")
        # 00:30 UTC = 01:30 Algiers (UTC+1) on the same calendar day in Algiers.
        # Before the fix, comparing raw UTC dates could treat this as "yesterday".
        fixed_utc_time = timezone.make_aware( 
            dt.datetime(2025, 6, 15, 0, 30, 0), timezone=__import__("datetime").timezone.utc
        )
        mock_now.return_value = fixed_utc_time

        note = DoctorNoteService.create_note(
            clinic=self.clinic, patient=self.patient, doctor=self.doctor, content="Original"
        )

        # Still "now" at the same mocked instant — must be editable.
        DoctorNoteService.update_note(note=note, doctor=self.doctor, content="Edited")

        note.refresh_from_db()
        self.assertEqual(note.content, "Edited")