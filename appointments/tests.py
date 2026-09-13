from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from datetime import datetime
from unittest.mock import patch


from accounts.models import User
from clinics.models import Clinic, Specialty
from clinics.profiles import DoctorProfile
from patients.models import Patient

from .models import Appointment, AppointmentType
from .services import AppointmentService, AppointmentTypeService


class AppointmentServiceTests(TestCase):

    def setUp(self):
        self.clinic_a = Clinic.objects.create(name="Clinic A")
        self.clinic_b = Clinic.objects.create(name="Clinic B")
        self.specialty = Specialty.objects.create(name="General Medicine")
        self.appt_type = AppointmentType.objects.create(name="Consultation")

        self.doctor_user_a = User.objects.create_user( #type:ignore
            email="doc-a@example.com", password="pw", clinic=self.clinic_a
        )
        self.doctor_a = DoctorProfile.objects.create(
            user=self.doctor_user_a, clinic=self.clinic_a, specialty=self.specialty
        )

        self.doctor_user_b = User.objects.create_user( #type:ignore
            email="doc-b@example.com", password="pw", clinic=self.clinic_b
        )
        self.doctor_b = DoctorProfile.objects.create(
            user=self.doctor_user_b, clinic=self.clinic_b, specialty=self.specialty
        )

        self.patient_a = Patient.objects.create(
            clinic=self.clinic_a, first_name="John", last_name="A"
        )
        self.patient_b = Patient.objects.create(
            clinic=self.clinic_b, first_name="Jane", last_name="B"
        )

    def test_create_appointment_defaults_to_scheduled(self):
        appt = AppointmentService.create_appointment(
            clinic=self.clinic_a,
            patient=self.patient_a,
            doctor=self.doctor_a,
            appointment_type=self.appt_type,
            scheduled_at=timezone.now() + timedelta(days=1),
            created_by=self.doctor_user_a,
        )

        self.assertEqual(appt.status, Appointment.Status.SCHEDULED)
        self.assertFalse(appt.is_walk_in)
        self.assertEqual(appt.type, self.appt_type)

    def test_create_walk_in_defaults_to_waiting(self):
        appt = AppointmentService.create_walk_in(
            clinic=self.clinic_a,
            patient=self.patient_a,
            doctor=self.doctor_a,
            appointment_type=self.appt_type,
            created_by=self.doctor_user_a,
        )

        self.assertEqual(appt.status, Appointment.Status.WAITING)
        self.assertTrue(appt.is_walk_in)

    def test_cannot_book_appointment_with_cross_clinic_doctor(self):
        with self.assertRaises(ValueError):
            AppointmentService.create_appointment(
                clinic=self.clinic_a,
                patient=self.patient_a,
                doctor=self.doctor_b,
                appointment_type=self.appt_type,
                scheduled_at=timezone.now() + timedelta(days=1),
                created_by=self.doctor_user_a,
            )

    def test_cannot_book_appointment_with_cross_clinic_patient(self):
        with self.assertRaises(ValueError):
            AppointmentService.create_appointment(
                clinic=self.clinic_a,
                patient=self.patient_b,
                doctor=self.doctor_a,
                appointment_type=self.appt_type,
                scheduled_at=timezone.now() + timedelta(days=1),
                created_by=self.doctor_user_a,
            )

    def test_cannot_book_appointment_in_the_past(self):
        with self.assertRaises(ValidationError):
            AppointmentService.create_appointment(
                clinic=self.clinic_a,
                patient=self.patient_a,
                doctor=self.doctor_a,
                appointment_type=self.appt_type,
                scheduled_at=timezone.now() - timedelta(days=1),
                created_by=self.doctor_user_a,
            )

        self.assertEqual(Appointment.objects.count(), 0)

    def test_get_for_day_only_returns_own_clinic(self):
        AppointmentService.create_walk_in(
            clinic=self.clinic_a, patient=self.patient_a,
            doctor=self.doctor_a, appointment_type=self.appt_type, created_by=self.doctor_user_a,
        )
        AppointmentService.create_walk_in(
            clinic=self.clinic_b, patient=self.patient_b,
            doctor=self.doctor_b, appointment_type=self.appt_type, created_by=self.doctor_user_b,
        )

        today_a = AppointmentService.get_for_day(self.clinic_a, timezone.localdate())

        self.assertEqual(today_a.count(), 1)
        self.assertEqual(today_a.first().clinic, self.clinic_a)

    @patch("django.utils.timezone.now")
    def test_get_for_day_includes_both_scheduled_and_walk_in(self, mock_now):
        fixed_now = timezone.make_aware(datetime(2025, 6, 15, 12, 0, 0))
        mock_now.return_value = fixed_now

        AppointmentService.create_appointment(
            clinic=self.clinic_a, patient=self.patient_a, doctor=self.doctor_a,
            appointment_type=self.appt_type,
            scheduled_at=fixed_now + timedelta(hours=1), created_by=self.doctor_user_a,
        )
        AppointmentService.create_walk_in(
            clinic=self.clinic_a, patient=self.patient_a,
            doctor=self.doctor_a, appointment_type=self.appt_type, created_by=self.doctor_user_a,
        )

        today_a = AppointmentService.get_for_day(self.clinic_a, fixed_now.date())

        self.assertEqual(today_a.count(), 2)

    def test_get_for_patient_filters_by_search(self):
        colonoscopy = AppointmentType.objects.create(name="Colonoscopy")

        AppointmentService.create_walk_in(
            clinic=self.clinic_a, patient=self.patient_a,
            doctor=self.doctor_a, appointment_type=self.appt_type, created_by=self.doctor_user_a,
        )
        AppointmentService.create_walk_in(
            clinic=self.clinic_a, patient=self.patient_a,
            doctor=self.doctor_a, appointment_type=colonoscopy, created_by=self.doctor_user_a,
        )

        results = AppointmentService.get_for_patient(self.clinic_a, self.patient_a, search="colono")

        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().type, colonoscopy)

    def test_update_status_rejects_invalid_value(self):
        appt = AppointmentService.create_walk_in(
            clinic=self.clinic_a, patient=self.patient_a,
            doctor=self.doctor_a, appointment_type=self.appt_type, created_by=self.doctor_user_a,
        )

        with self.assertRaises(ValueError):
            AppointmentService.update_status(appointment=appt, new_status="not_a_real_status")

    def test_update_status_accepts_valid_value(self):
        appt = AppointmentService.create_walk_in(
            clinic=self.clinic_a, patient=self.patient_a,
            doctor=self.doctor_a, appointment_type=self.appt_type, created_by=self.doctor_user_a,
        )

        AppointmentService.update_status(appointment=appt, new_status=Appointment.Status.WITH_DOCTOR)

        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.WITH_DOCTOR)


class AppointmentTypeServiceTests(TestCase):

    def test_register_and_reuse_case_insensitively(self):
        first = AppointmentTypeService.get_or_create("Colonoscopy")
        second = AppointmentTypeService.get_or_create("colonoscopy")

        self.assertEqual(first.pk, second.pk) #type:ignore
        self.assertEqual(AppointmentType.objects.count(), 1)

    def test_suggest_filters_by_query(self):
        AppointmentType.objects.create(name="Colonoscopy")
        AppointmentType.objects.create(name="Consultation")

        results = AppointmentTypeService.suggest("colo")

        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().name, "Colonoscopy") #type:ignore


class AppointmentViewTests(TestCase):

    def setUp(self):
        self.clinic_a = Clinic.objects.create(name="Clinic A")
        self.clinic_b = Clinic.objects.create(name="Clinic B")
        self.specialty = Specialty.objects.create(name="General Medicine")

        self.user = User.objects.create_user( #type:ignore
            email="staff-a@example.com", password="StrongPassword123!", clinic=self.clinic_a
        )
        self.doctor = DoctorProfile.objects.create(
            user=self.user, clinic=self.clinic_a, specialty=self.specialty
        )
        self.patient = Patient.objects.create(
            clinic=self.clinic_a, first_name="John", last_name="A"
        )

        self.no_clinic_user = User.objects.create_user( #type:ignore
            email="no-clinic@example.com", password="StrongPassword123!"
        )

    def test_day_view_requires_login(self):
        response = self.client.get(reverse("appointments:day"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url) #type:ignore

    def test_user_without_clinic_cannot_view_day(self):
        self.client.login(email="no-clinic@example.com", password="StrongPassword123!")

        response = self.client.get(reverse("appointments:day"))

        self.assertEqual(response.status_code, 403)

    def test_user_without_clinic_cannot_add_appointment(self):
        self.client.login(email="no-clinic@example.com", password="StrongPassword123!")

        response = self.client.get(reverse("appointments:add"))

        self.assertEqual(response.status_code, 403)

    def test_add_walk_in_creates_waiting_appointment(self):
        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        response = self.client.post(
            reverse("appointments:walk_in"),
            {"patient": self.patient.pk, "doctor": self.doctor.pk, "type": "Consultation"},
        )

        self.assertRedirects(response, reverse("appointments:day"))

        appt = Appointment.objects.get(patient=self.patient)
        self.assertEqual(appt.status, Appointment.Status.WAITING)
        self.assertTrue(appt.is_walk_in)
        self.assertEqual(appt.type.name, "Consultation")

    def test_add_appointment_with_future_date_succeeds(self):
        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        future = timezone.now() + timedelta(days=1)

        response = self.client.post(
            reverse("appointments:add"),
            {
                "patient": self.patient.pk,
                "doctor": self.doctor.pk,
                "type": "Consultation",
                "scheduled_at": future.strftime("%Y-%m-%dT%H:%M"),
            },
        )

        self.assertRedirects(response, reverse("appointments:day"))
        self.assertEqual(Appointment.objects.filter(patient=self.patient).count(), 1)

    def test_add_appointment_with_past_date_fails(self):
        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        past = timezone.now() - timedelta(days=1)

        response = self.client.post(
            reverse("appointments:add"),
            {
                "patient": self.patient.pk,
                "doctor": self.doctor.pk,
                "type": "Consultation",
                "scheduled_at": past.strftime("%Y-%m-%dT%H:%M"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())
        self.assertIn("scheduled_at", response.context["form"].errors)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_add_appointment_requires_type(self):
        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        future = timezone.now() + timedelta(days=1)

        response = self.client.post(
            reverse("appointments:add"),
            {
                "patient": self.patient.pk,
                "doctor": self.doctor.pk,
                "type": "",
                "scheduled_at": future.strftime("%Y-%m-%dT%H:%M"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())
        self.assertIn("type", response.context["form"].errors)

    def test_add_appointment_form_only_lists_own_clinic_patients_and_doctors(self):
        other_specialty = Specialty.objects.create(name="Cardiology")
        other_user = User.objects.create_user(
            email="doc-b@example.com", password="pw", clinic=self.clinic_b #type:ignore
        )
        other_doctor = DoctorProfile.objects.create(
            user=other_user, clinic=self.clinic_b, specialty=other_specialty
        )
        Patient.objects.create(clinic=self.clinic_b, first_name="Jane", last_name="B")

        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        response = self.client.get(reverse("appointments:add"))

        form = response.context["form"]
        self.assertIn(self.patient, form.fields["patient"].queryset)
        self.assertIn(self.doctor, form.fields["doctor"].queryset)
        self.assertNotIn(other_doctor, form.fields["doctor"].queryset)

    def test_add_appointment_prefills_patient_from_query_param(self):
        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        response = self.client.get(reverse("appointments:add") + f"?patient={self.patient.pk}")

        self.assertEqual(str(response.context["form"].initial.get("patient")), str(self.patient.pk))

    def test_add_appointment_redirects_to_next_when_provided(self):
        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        future = timezone.now() + timedelta(days=1)
        next_path = f"/patients/{self.patient.pk}/"

        response = self.client.post(reverse("appointments:add"), {
            "patient": self.patient.pk,
            "doctor": self.doctor.pk,
            "type": "Consultation",
            "scheduled_at": future.strftime("%Y-%m-%dT%H:%M"),
            "next": next_path,
        })

        self.assertRedirects(response, next_path, fetch_redirect_response=False)

    def test_update_status_via_post(self):
        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        appt = AppointmentService.create_walk_in(
            clinic=self.clinic_a, patient=self.patient,
            doctor=self.doctor, appointment_type=AppointmentType.objects.create(name="Consultation"),
            created_by=self.user,
        )

        response = self.client.post(
            reverse("appointments:update_status", args=[appt.pk]),
            {"status": Appointment.Status.WITH_DOCTOR},
        )

        self.assertRedirects(response, reverse("appointments:day"))

        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.WITH_DOCTOR)

    def test_update_status_rejects_appointment_from_other_clinic(self):
        other_specialty = Specialty.objects.create(name="Cardiology")
        other_user = User.objects.create_user( #type:ignore
            email="doc-b@example.com", password="pw", clinic=self.clinic_b
        )
        other_doctor = DoctorProfile.objects.create(
            user=other_user, clinic=self.clinic_b, specialty=other_specialty
        )
        other_patient = Patient.objects.create(
            clinic=self.clinic_b, first_name="Jane", last_name="B"
        )
        other_appt = AppointmentService.create_walk_in(
            clinic=self.clinic_b, patient=other_patient,
            doctor=other_doctor, appointment_type=AppointmentType.objects.create(name="Consultation"),
            created_by=other_user,
        )

        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        response = self.client.post(
            reverse("appointments:update_status", args=[other_appt.pk]),
            {"status": Appointment.Status.WITH_DOCTOR},
        )

        self.assertEqual(response.status_code, 404)

        other_appt.refresh_from_db()
        self.assertEqual(other_appt.status, Appointment.Status.WAITING)

    def test_deactivated_doctor_not_in_appointment_form_dropdown(self):
        other_doctor_user = User.objects.create_user( #type:ignore
            email="inactive-doc@example.com", password="pw", clinic=self.clinic_a
        )
        other_doctor = DoctorProfile.objects.create(
            user=other_doctor_user, clinic=self.clinic_a, specialty=self.specialty
        )
        other_doctor_user.is_active = False
        other_doctor_user.save()

        self.client.login(email="staff-a@example.com", password="StrongPassword123!")

        response = self.client.get(reverse("appointments:add"))

        form = response.context["form"]
        self.assertIn(self.doctor, form.fields["doctor"].queryset)
        self.assertNotIn(other_doctor, form.fields["doctor"].queryset)
class AppointmentTypeSuggestViewTests(TestCase):

    def setUp(self):
        self.clinic = Clinic.objects.create(name="Clinic A")
        self.user = User.objects.create_user(
            email="staff@example.com", password="StrongPassword123!", clinic=self.clinic #type:ignore
        )
        AppointmentType.objects.create(name="Colonoscopy")
        AppointmentType.objects.create(name="Consultation")

    def test_suggest_requires_login(self):
        response = self.client.get(reverse("appointments:type_suggest"), {"q": "colo"})
        self.assertEqual(response.status_code, 302)

    def test_suggest_returns_matching_names(self):
        self.client.login(email="staff@example.com", password="StrongPassword123!")

        response = self.client.get(reverse("appointments:type_suggest"), {"q": "colo"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"results": ["Colonoscopy"]})


class AppointmentEditViewTests(TestCase):

    def setUp(self):
        self.clinic = Clinic.objects.create(name="Clinic A")
        self.specialty = Specialty.objects.create(name="General Medicine")
        self.user = User.objects.create_user( #type:ignore
            email="staff@example.com", password="StrongPassword123!", clinic=self.clinic
        )
        self.doctor = DoctorProfile.objects.create(user=self.user, clinic=self.clinic, specialty=self.specialty)
        self.other_doctor_user = User.objects.create_user( #type:ignore
            email="doc2@example.com", password="pw", clinic=self.clinic
        )
        self.other_doctor = DoctorProfile.objects.create(
            user=self.other_doctor_user, clinic=self.clinic, specialty=self.specialty
        )
        self.patient = Patient.objects.create(clinic=self.clinic, first_name="John", last_name="A")
        self.appt_type = AppointmentType.objects.create(name="Consultation")

    def test_can_edit_scheduled_appointment(self):
        appt = AppointmentService.create_appointment(
            clinic=self.clinic, patient=self.patient, doctor=self.doctor,
            appointment_type=self.appt_type, scheduled_at=timezone.now() + timedelta(days=1),
            created_by=self.user,
        )

        self.client.login(email="staff@example.com", password="StrongPassword123!")

        new_time = timezone.now() + timedelta(days=2)
        response = self.client.post(reverse("appointments:edit", args=[appt.pk]), {
            "doctor": self.other_doctor.pk,
            "type": "Follow-up",
            "scheduled_at": new_time.strftime("%Y-%m-%dT%H:%M"),
        })

        self.assertRedirects(response, reverse("patients:detail", args=[self.patient.pk]))

        appt.refresh_from_db()
        self.assertEqual(appt.doctor, self.other_doctor)
        self.assertEqual(appt.type.name, "Follow-up")

    def test_cannot_edit_done_appointment(self):
        appt = AppointmentService.create_walk_in(
        clinic=self.clinic, patient=self.patient, doctor=self.doctor,
        appointment_type=self.appt_type, created_by=self.user,
        )
        AppointmentService.update_status(appointment=appt, new_status="done")

        self.client.login(email="staff@example.com", password="StrongPassword123!")

        response = self.client.post(reverse("appointments:edit", args=[appt.pk]), {
            "doctor": self.other_doctor.pk,
            "type": "Follow-up",
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn("already been completed", str(response.context["form"].errors))

        appt.refresh_from_db()
        self.assertEqual(appt.doctor, self.doctor) 

    def test_walk_in_scheduled_at_is_not_editable(self):
        appt = AppointmentService.create_walk_in(
            clinic=self.clinic, patient=self.patient, doctor=self.doctor,
            appointment_type=self.appt_type, created_by=self.user,
        )
        original_time = appt.scheduled_at

        self.client.login(email="staff@example.com", password="StrongPassword123!")

        self.client.post(reverse("appointments:edit", args=[appt.pk]), {
            "doctor": self.doctor.pk,
            "type": "Consultation",
        })

        appt.refresh_from_db()
        self.assertEqual(appt.scheduled_at, original_time)

    def test_editing_scheduled_appointment_with_blank_date_shows_error_not_crash(self):
        appt = AppointmentService.create_appointment(
            clinic=self.clinic, patient=self.patient, doctor=self.doctor,
            appointment_type=self.appt_type, scheduled_at=timezone.now() + timedelta(days=1),
            created_by=self.user,
        )

        self.client.login(email="staff@example.com", password="StrongPassword123!")

        # Deliberately omit scheduled_at entirely — this is a non-walk-in appointment,
        # so the service must reject this cleanly rather than crash on None < now().
        response = self.client.post(reverse("appointments:edit", args=[appt.pk]), {
            "doctor": self.doctor.pk,
            "type": "Consultation",
        })

        self.assertEqual(response.status_code, 200)  # not 500
        self.assertIn("required for a scheduled appointment", str(response.context["form"].errors))

        appt.refresh_from_db()
        self.assertEqual(appt.doctor, self.doctor)  # unchanged