from django.test import TestCase

from clinics.forms import ClinicRegistrationForm
# Create your tests here.


from accounts.models import User
from clinics.models import Clinic, Specialty
from clinics.profiles import DoctorProfile, SecretaryProfile
from clinics.services import ClinicService, StaffService

from patients.models import Patient

from django.urls import reverse

class ClinicServiceTests(TestCase):
    def setUp(self):
        self.specialty = Specialty.objects.create(name="General Medicine")

    def test_create_clinic_creates_doctor_admin(self):
        clinic, doctor = ClinicService.create_clinic(
            clinic_name="My Medical Clinic",
            doctor_email="doctor@example.com",
            password="StrongPassword123!",
            first_name="John",
            last_name="Doe",
            specialty=self.specialty
        )
        user = doctor.user

        self.assertIsNotNone(clinic)
        self.assertIsNotNone(doctor)

        

        self.assertEqual(clinic.name, "My Medical Clinic")

        self.assertEqual(user.email, "doctor@example.com")

        self.assertEqual(user.role, user.Role.DOCTOR)

        self.assertTrue(user.is_clinic_admin)

        self.assertEqual(user.clinic, clinic)

        self.assertEqual(doctor.clinic, clinic)

        self.assertEqual(doctor.specialty, self.specialty)

        self.assertTrue(user.check_password("StrongPassword123!"))



class ClinicRegistrationFormTests(TestCase):

    def setUp(self):
        self.specialty = Specialty.objects.create(name="General Medicine")

    def test_valid_registration_form(self):
        form = ClinicRegistrationForm(
            data={
                "clinic_name": "My Clinic",
                "clinic_phone": "0555123456",
                "clinic_address": "Annaba",
                "first_name": "John",
                "last_name": "Doe",
                "email": "doctor@example.com",
                "password": "StrongPassword123!",
                "password_confirm": "StrongPassword123!",
                "specialty": self.specialty.name,   # <-- was self.specialty.pk
            }
        )

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["specialty"], self.specialty)

    def test_registration_reuses_existing_specialty_case_insensitively(self):
        form = ClinicRegistrationForm(
            data={
                "clinic_name": "My Clinic",
                "clinic_phone": "",
                "clinic_address": "",
                "first_name": "John",
                "last_name": "Doe",
                "email": "doctor2@example.com",
                "password": "StrongPassword123!",
                "password_confirm": "StrongPassword123!",
                "specialty": "general medicine",   # different case
            }
        )

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["specialty"], self.specialty)
        self.assertEqual(Specialty.objects.filter(name__iexact="general medicine").count(), 1)

    def test_registration_creates_new_specialty_if_not_found(self):
        form = ClinicRegistrationForm(
            data={
                "clinic_name": "My Clinic",
                "clinic_phone": "",
                "clinic_address": "",
                "first_name": "John",
                "last_name": "Doe",
                "email": "doctor3@example.com",
                "password": "StrongPassword123!",
                "password_confirm": "StrongPassword123!",
                "specialty": "Dermatology",
            }
        )

        self.assertTrue(form.is_valid())

        specialty = form.cleaned_data["specialty"]
        self.assertEqual(specialty.name, "Dermatology")
        self.assertTrue(Specialty.objects.filter(name="Dermatology", is_active=True).exists())

    def test_registration_requires_specialty(self):
        form = ClinicRegistrationForm(
            data={
                "clinic_name": "My Clinic",
                "first_name": "John",
                "last_name": "Doe",
                "email": "doctor4@example.com",
                "password": "StrongPassword123!",
                "password_confirm": "StrongPassword123!",
                "specialty": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("specialty", form.errors)


class SpecialtySuggestViewTests(TestCase):

    def setUp(self):
        Specialty.objects.create(name="Cardiology", is_active=True)
        Specialty.objects.create(name="Dermatology", is_active=True)
        Specialty.objects.create(name="Retired Specialty", is_active=False)

    def test_suggest_works_without_login(self):
        response = self.client.get(reverse("clinics:specialty_suggest"), {"q": "cardio"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"results": ["Cardiology"]})

    def test_suggest_excludes_inactive_specialties(self):
        response = self.client.get(reverse("clinics:specialty_suggest"), {"q": "retired"})

        self.assertEqual(response.json(), {"results": []})

    def test_suggest_returns_empty_for_blank_query(self):
        response = self.client.get(reverse("clinics:specialty_suggest"), {"q": ""}) #type:ignore

        self.assertEqual(response.json(), {"results": []})

class TenantIsolationTests(TestCase):

    def setUp(self):
        self.clinic_a = Clinic.objects.create(name="Clinic A")
        self.clinic_b = Clinic.objects.create(name="Clinic B")

        self.patient_a = Patient.objects.create(clinic=self.clinic_a, first_name="John", last_name="Patient")
        self.patient_b = Patient.objects.create(clinic=self.clinic_b, first_name="Jane", last_name="Patient")

    def test_clinic_a_only_gets_its_patients(self):
        patients = Patient.objects.for_clinic(self.clinic_a) #type:ignore

        self.assertEqual( patients.count(), 1)
        self.assertEqual( patients.first(), self.patient_a)
        self.assertNotIn( self.patient_b, patients)
        

    def test_clinic_b_only_gets_its_patients(self): 

        patients = Patient.objects.for_clinic( self.clinic_b )  #type:ignore

        self.assertEqual( patients.count(), 1, ) 
        self.assertEqual( patients.first(), self.patient_b, ) 
        self.assertNotIn( self.patient_a, patients, )


class StaffServiceTests(TestCase):

    def setUp(self):
        self.clinic = Clinic.objects.create(name="Clinic A")
        self.specialty = Specialty.objects.create(name="General Medicine")

        self.admin_user = User.objects.create_clinic_admin( #type:ignore
            email="admin@example.com", password="pw", clinic=self.clinic,
            first_name="Admin", last_name="Doc",
        )
        self.admin_doctor = DoctorProfile.objects.create(
            user=self.admin_user, clinic=self.clinic, specialty=self.specialty
        )

    def test_create_doctor(self):
        doctor = StaffService.create_doctor(
            clinic=self.clinic, email="new@example.com", password="StrongPassword123!",
            first_name="New", last_name="Doc", specialty=self.specialty,
        )

        self.assertFalse(doctor.user.is_clinic_admin)
        self.assertEqual(doctor.user.role, User.Role.DOCTOR)
        self.assertEqual(doctor.clinic, self.clinic)

    def test_create_secretary_requires_creating_doctor_same_clinic(self):
        other_clinic = Clinic.objects.create(name="Clinic B")
        other_admin = User.objects.create_clinic_admin( #type:ignore
            email="other@example.com", password="pw", clinic=other_clinic,
        )
        other_doctor = DoctorProfile.objects.create(
            user=other_admin, clinic=other_clinic, specialty=self.specialty
        )

        with self.assertRaises(ValueError):
            StaffService.create_secretary(
                clinic=self.clinic, created_by=other_doctor,
                email="sec@example.com", password="StrongPassword123!",
                first_name="Sec", last_name="Retary",
            )

    def test_create_secretary(self):
        secretary = StaffService.create_secretary(
            clinic=self.clinic, created_by=self.admin_doctor,
            email="sec@example.com", password="StrongPassword123!",
            first_name="Sec", last_name="Retary",
        )

        self.assertEqual(secretary.created_by, self.admin_doctor)
        self.assertEqual(secretary.user.role, User.Role.SECRETARY)


class StaffViewTests(TestCase):

    def setUp(self):
        self.clinic = Clinic.objects.create(name="Clinic A")
        self.specialty = Specialty.objects.create(name="General Medicine")

        self.admin_user = User.objects.create_clinic_admin( #type:ignore
            email="admin@example.com", password="StrongPassword123!", clinic=self.clinic,
        )
        self.admin_doctor = DoctorProfile.objects.create(
            user=self.admin_user, clinic=self.clinic, specialty=self.specialty
        )

        self.regular_doctor_user = User.objects.create_doctor( #type:ignore
            email="regular@example.com", password="StrongPassword123!", clinic=self.clinic,
        )
        DoctorProfile.objects.create(
            user=self.regular_doctor_user, clinic=self.clinic, specialty=self.specialty
        )

    def test_non_admin_doctor_cannot_add_doctor(self):
        self.client.login(email="regular@example.com", password="StrongPassword123!")

        response = self.client.get(reverse("clinics:doctor_add"))

        self.assertEqual(response.status_code, 403)

    def test_admin_can_add_doctor(self):
        self.client.login(email="admin@example.com", password="StrongPassword123!")

        response = self.client.post(reverse("clinics:doctor_add"), {
            "first_name": "New", "last_name": "Doc",
            "email": "newdoc@example.com",
            "password": "StrongPassword123!", "password_confirm": "StrongPassword123!",
            "specialty": "Cardiology",
        })

        self.assertRedirects(response, reverse("clinics:doctor_list"))
        self.assertTrue(User.objects.filter(email="newdoc@example.com").exists())

    def test_admin_can_add_secretary(self):
        self.client.login(email="admin@example.com", password="StrongPassword123!")

        response = self.client.post(reverse("clinics:secretary_add"), {
            "first_name": "New", "last_name": "Sec",
            "email": "newsec@example.com",
            "password": "StrongPassword123!", "password_confirm": "StrongPassword123!",
        })

        self.assertRedirects(response, reverse("clinics:secretary_list"))
        self.assertTrue(User.objects.filter(email="newsec@example.com").exists())


class ClinicSettingsViewTests(TestCase):

    def setUp(self):
        self.clinic = Clinic.objects.create(name="Old Name", phone="0555000000")
        self.specialty = Specialty.objects.create(name="General Medicine")

        self.admin_user = User.objects.create_clinic_admin( #type:ignore
            email="admin@example.com", password="StrongPassword123!", clinic=self.clinic,
        )
        DoctorProfile.objects.create(user=self.admin_user, clinic=self.clinic, specialty=self.specialty)

        self.regular_doctor_user = User.objects.create_doctor( #type:ignore
            email="regular@example.com", password="StrongPassword123!", clinic=self.clinic,
        )
        DoctorProfile.objects.create(user=self.regular_doctor_user, clinic=self.clinic, specialty=self.specialty)

    def test_requires_login(self):
        response = self.client.get(reverse("clinics:settings"))
        self.assertEqual(response.status_code, 302)

    def test_non_admin_cannot_access(self):
        self.client.login(email="regular@example.com", password="StrongPassword123!")

        response = self.client.get(reverse("clinics:settings"))

        self.assertEqual(response.status_code, 403)

    def test_admin_can_view_settings(self):
        self.client.login(email="admin@example.com", password="StrongPassword123!")

        response = self.client.get(reverse("clinics:settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Old Name")

    def test_admin_can_update_clinic_info_and_letterhead(self):
        self.client.login(email="admin@example.com", password="StrongPassword123!")

        response = self.client.post(reverse("clinics:settings"), {
            "name": "New Clinic Name",
            "phone": "0555111111",
            "address": "123 Main St",
            "document_header": "Confidential Medical Document",
            "document_footer": "Thank you for choosing our clinic",
        })

        self.assertRedirects(response, reverse("clinics:settings"))

        self.clinic.refresh_from_db()
        self.assertEqual(self.clinic.name, "New Clinic Name")
        self.assertEqual(self.clinic.document_header, "Confidential Medical Document")



class StaffDetailAndDeactivateTests(TestCase):

    def setUp(self):
        self.clinic = Clinic.objects.create(name="Clinic A")
        self.other_clinic = Clinic.objects.create(name="Clinic B")
        self.specialty = Specialty.objects.create(name="General Medicine")

        self.admin_user = User.objects.create_clinic_admin( #type:ignore
            email="admin@example.com", password="StrongPassword123!", clinic=self.clinic,
        )
        self.admin_doctor = DoctorProfile.objects.create(
            user=self.admin_user, clinic=self.clinic, specialty=self.specialty
        )

        self.other_doctor_user = User.objects.create_doctor( #type:ignore
            email="other-doc@example.com", password="StrongPassword123!", clinic=self.clinic,
        )
        self.other_doctor = DoctorProfile.objects.create(
            user=self.other_doctor_user, clinic=self.clinic, specialty=self.specialty
        )

        self.secretary_user = User.objects.create_secretary( #type:ignore
            email="sec@example.com", password="StrongPassword123!", clinic=self.clinic,
        )
        self.secretary = SecretaryProfile.objects.create(
            user=self.secretary_user, clinic=self.clinic, created_by=self.admin_doctor
        )

    def test_doctor_detail_requires_admin(self):
        self.client.login(email="other-doc@example.com", password="StrongPassword123!")

        response = self.client.get(reverse("clinics:doctor_detail", args=[self.other_doctor.pk]))

        self.assertEqual(response.status_code, 403)

    def test_admin_can_view_doctor_detail(self):
        self.client.login(email="admin@example.com", password="StrongPassword123!")

        response = self.client.get(reverse("clinics:doctor_detail", args=[self.other_doctor.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "other-doc@example.com")

    def test_doctor_detail_404_for_other_clinic(self):
        other_specialty = Specialty.objects.create(name="Cardiology")
        other_admin = User.objects.create_clinic_admin( #type:ignore
            email="other-admin@example.com", password="StrongPassword123!", clinic=self.other_clinic,
        )
        other_doctor = DoctorProfile.objects.create(
            user=other_admin, clinic=self.other_clinic, specialty=other_specialty
        )

        self.client.login(email="admin@example.com", password="StrongPassword123!")

        response = self.client.get(reverse("clinics:doctor_detail", args=[other_doctor.pk]))

        self.assertEqual(response.status_code, 404)

    def test_admin_can_deactivate_doctor(self):
        self.client.login(email="admin@example.com", password="StrongPassword123!")

        response = self.client.post(reverse("clinics:doctor_toggle_active", args=[self.other_doctor.pk]))

        self.assertRedirects(response, reverse("clinics:doctor_detail", args=[self.other_doctor.pk]))

        self.other_doctor_user.refresh_from_db()
        self.assertFalse(self.other_doctor_user.is_active)

    def test_deactivated_doctor_cannot_log_in(self):
        self.client.login(email="admin@example.com", password="StrongPassword123!")
        self.client.post(reverse("clinics:doctor_toggle_active", args=[self.other_doctor.pk]))
        self.client.logout()

        response = self.client.post(reverse("accounts:login"), {
            "email": "other-doc@example.com", "password": "StrongPassword123!",
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_toggle_reactivates_inactive_doctor(self):
        self.other_doctor_user.is_active = False
        self.other_doctor_user.save()

        self.client.login(email="admin@example.com", password="StrongPassword123!")
        self.client.post(reverse("clinics:doctor_toggle_active", args=[self.other_doctor.pk]))

        self.other_doctor_user.refresh_from_db()
        self.assertTrue(self.other_doctor_user.is_active)

    def test_cannot_deactivate_clinic_admin(self):
        self.client.login(email="admin@example.com", password="StrongPassword123!")

        response = self.client.post(reverse("clinics:doctor_toggle_active", args=[self.admin_doctor.pk]))

        self.assertRedirects(response, reverse("clinics:doctor_detail", args=[self.admin_doctor.pk]))

        self.admin_user.refresh_from_db()
        self.assertTrue(self.admin_user.is_active)

    def test_admin_can_deactivate_secretary(self):
        self.client.login(email="admin@example.com", password="StrongPassword123!")

        response = self.client.post(reverse("clinics:secretary_toggle_active", args=[self.secretary.pk]))

        self.assertRedirects(response, reverse("clinics:secretary_detail", args=[self.secretary.pk]))

        self.secretary_user.refresh_from_db()
        self.assertFalse(self.secretary_user.is_active)

    def test_secretary_detail_requires_admin(self):
        self.client.login(email="sec@example.com", password="StrongPassword123!")

        response = self.client.get(reverse("clinics:secretary_detail", args=[self.secretary.pk]))

        self.assertEqual(response.status_code, 403)

    def test_deactivating_doctor_ends_their_active_session(self):
        # Log in as the doctor who is about to be deactivated
        self.client.login(email="other-doc@example.com", password="StrongPassword123!")

        # Confirm the session actually works before deactivation
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)

        # A separate client acts as the admin deactivating them,
        # so the doctor's own session/cookies aren't touched by this call.
        from django.test import Client
        admin_client = Client()
        admin_client.login(email="admin@example.com", password="StrongPassword123!")
        admin_client.post(reverse("clinics:doctor_toggle_active", args=[self.other_doctor.pk]))

        # The doctor's original session should now be dead, not just
        # blocked at next login — this request should redirect to login.
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url) #type:ignore
