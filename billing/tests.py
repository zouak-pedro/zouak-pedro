# billing/tests.py
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from clinics.models import Clinic, Specialty
from clinics.profiles import DoctorProfile
from clinics.services import ClinicService, StaffService
from patients.models import Patient
from patients.services import PatientService
from appointments.models import AppointmentType
from appointments.services import AppointmentService

from .models import (Subscription, VisitRecord, Invoice, PlanChangeCheckout,
                     PlanChangeRequest, PaymentInstructions)
from .services import (PaymentInstructionsService, SubscriptionService, BillingService,
                        InvoiceService, PlanRequestService, PlanChangeCheckoutService)

from django.core.files.uploadedfile import SimpleUploadedFile

from django.core.exceptions import ValidationError 
from billing.tasks import generate_monthly_invoices



class SubscriptionServiceTests(TestCase):

    def setUp(self):
        self.specialty = Specialty.objects.create(name="General Medicine")

    def test_create_clinic_starts_a_trial(self):
        clinic, doctor = ClinicService.create_clinic(
            clinic_name="Test Clinic", doctor_email="d@example.com", password="pw",
            first_name="J", last_name="D", specialty=self.specialty,
        )

        sub = SubscriptionService.get_subscription(clinic)
        self.assertEqual(sub.plan, Subscription.Plan.TRIAL) #type:ignore
        self.assertEqual(sub.status, Subscription.Status.TRIALING) #type:ignore
        self.assertIsNotNone(sub.trial_ends_at) #type:ignore

    def test_trial_patient_cap_enforced(self):
        clinic, doctor = ClinicService.create_clinic(
            clinic_name="Test Clinic", doctor_email="d@example.com", password="pw",
            first_name="J", last_name="D", specialty=self.specialty,
        )

        for i in range(50):
            PatientService.create_patient(clinic=clinic, first_name=f"P{i}", last_name="X")

        with self.assertRaises(ValueError):
            PatientService.create_patient(clinic=clinic, first_name="One Too Many", last_name="X")

    def test_standard_plan_has_no_patient_cap(self):
        clinic, doctor = ClinicService.create_clinic(
            clinic_name="Test Clinic", doctor_email="d@example.com", password="pw",
            first_name="J", last_name="D", specialty=self.specialty,
        )
        sub = SubscriptionService.get_subscription(clinic)
        sub.plan = Subscription.Plan.STANDARD #type:ignore
        sub.status = Subscription.Status.ACTIVE #type:ignore
        sub.save() #type:ignore

        for i in range(55):
            PatientService.create_patient(clinic=clinic, first_name=f"P{i}", last_name="X")

        self.assertEqual(Patient.objects.filter(clinic=clinic).count(), 55)

    def test_standard_plan_caps_doctors_at_one(self):
        clinic, doctor = ClinicService.create_clinic(
            clinic_name="Test Clinic", doctor_email="admin@example.com", password="pw",
            first_name="J", last_name="D", specialty=self.specialty,
        )
        sub = SubscriptionService.get_subscription(clinic)
        sub.plan = Subscription.Plan.STANDARD #type:ignore
        sub.status = Subscription.Status.ACTIVE #type:ignore
        sub.save() #type:ignore

        with self.assertRaises(ValueError):
            StaffService.create_doctor(
                clinic=clinic, email="second@example.com", password="StrongPassword123!",
                first_name="Two", last_name="Doc", specialty=self.specialty,
            )

    def test_pay_per_visit_plan_has_no_doctor_cap(self):
        clinic, doctor = ClinicService.create_clinic(
            clinic_name="Test Clinic", doctor_email="admin@example.com", password="pw",
            first_name="J", last_name="D", specialty=self.specialty,
        )
        sub = SubscriptionService.get_subscription(clinic)
        sub.plan = Subscription.Plan.PAY_PER_VISIT #type:ignore
        sub.status = Subscription.Status.ACTIVE #type:ignore
        sub.save() #type:ignore

        StaffService.create_doctor(
            clinic=clinic, email="second@example.com", password="StrongPassword123!",
            first_name="Two", last_name="Doc", specialty=self.specialty,
        )

        self.assertEqual(DoctorProfile.objects.filter(clinic=clinic).count(), 2)


class BillingServiceTests(TestCase):

    def setUp(self):
        self.specialty = Specialty.objects.create(name="General Medicine")
        self.clinic, self.doctor = ClinicService.create_clinic(
            clinic_name="Test Clinic", doctor_email="d@example.com", password="pw",
            first_name="J", last_name="D", specialty=self.specialty,
        )
        sub = SubscriptionService.get_subscription(self.clinic)
        sub.plan = Subscription.Plan.PAY_PER_VISIT #type:ignore
        sub.status = Subscription.Status.ACTIVE #type:ignore
        sub.save() #type:ignore

        self.patient = Patient.objects.create(clinic=self.clinic, first_name="P", last_name="X")
        self.appt_type = AppointmentType.objects.create(name="Consultation")

    def test_walk_in_is_billed_immediately(self):
        appt = AppointmentService.create_walk_in(
            clinic=self.clinic, patient=self.patient, doctor=self.doctor,
            appointment_type=self.appt_type, created_by=self.doctor.user,
        )

        self.assertTrue(VisitRecord.objects.filter(appointment=appt).exists())
        self.assertEqual(VisitRecord.objects.get(appointment=appt).amount, Decimal("50.00"))

    def test_scheduled_appointment_not_billed_until_done(self):
        appt = AppointmentService.create_appointment(
            clinic=self.clinic, patient=self.patient, doctor=self.doctor,
            appointment_type=self.appt_type, scheduled_at=timezone.now() + timedelta(days=1),
            created_by=self.doctor.user,
        )

        self.assertFalse(VisitRecord.objects.filter(appointment=appt).exists())

        AppointmentService.update_status(appointment=appt, new_status="with_doctor")
        self.assertFalse(VisitRecord.objects.filter(appointment=appt).exists())

        AppointmentService.update_status(appointment=appt, new_status="done")
        self.assertTrue(VisitRecord.objects.filter(appointment=appt).exists())

    def test_cancelled_appointment_never_billed(self):
        appt = AppointmentService.create_appointment(
            clinic=self.clinic, patient=self.patient, doctor=self.doctor,
            appointment_type=self.appt_type, scheduled_at=timezone.now() + timedelta(days=1),
            created_by=self.doctor.user,
        )

        AppointmentService.update_status(appointment=appt, new_status="cancelled")

        self.assertFalse(VisitRecord.objects.filter(appointment=appt).exists())

    def test_record_visit_is_idempotent(self):
        appt = AppointmentService.create_walk_in(
            clinic=self.clinic, patient=self.patient, doctor=self.doctor,
            appointment_type=self.appt_type, created_by=self.doctor.user,
        )

        BillingService.record_visit(appt)
        BillingService.record_visit(appt)

        self.assertEqual(VisitRecord.objects.filter(appointment=appt).count(), 1)

    def test_standard_plan_never_creates_visit_records(self):
        sub = SubscriptionService.get_subscription(self.clinic)
        sub.plan = Subscription.Plan.STANDARD #type:ignore
        sub.save() #type:ignore

        appt = AppointmentService.create_walk_in(
            clinic=self.clinic, patient=self.patient, doctor=self.doctor,
            appointment_type=self.appt_type, created_by=self.doctor.user,
        )

        self.assertFalse(VisitRecord.objects.filter(appointment=appt).exists())


class InvoiceServiceTests(TestCase):

    def setUp(self):
        self.specialty = Specialty.objects.create(name="General Medicine")
        self.clinic, self.doctor = ClinicService.create_clinic(
            clinic_name="Test Clinic", doctor_email="d@example.com", password="pw",
            first_name="J", last_name="D", specialty=self.specialty,
        )
        self.patient = Patient.objects.create(clinic=self.clinic, first_name="P", last_name="X")
        self.appt_type = AppointmentType.objects.create(name="Consultation")

    def test_trial_generates_no_invoice(self):
        invoice = InvoiceService.generate_monthly_invoice(
            self.clinic, date(2025, 1, 1), date(2025, 1, 31)
        )
        self.assertIsNone(invoice)

    def test_standard_plan_generates_flat_fee_invoice(self):
        sub = SubscriptionService.get_subscription(self.clinic)
        sub.plan = Subscription.Plan.STANDARD #type:ignore
        sub.status = Subscription.Status.ACTIVE #type:ignore
        sub.save() #type:ignore

        invoice = InvoiceService.generate_monthly_invoice(
            self.clinic, date(2025, 1, 1), date(2025, 1, 31)
        )

        self.assertEqual(invoice.amount_due, Decimal("10000.00")) #type:ignore
        self.assertEqual(invoice.plan, Subscription.Plan.STANDARD) #type:ignore

    def test_pay_per_visit_invoice_sums_unbilled_visits(self):
        sub = SubscriptionService.get_subscription(self.clinic)
        sub.plan = Subscription.Plan.PAY_PER_VISIT #type:ignore
        sub.status = Subscription.Status.ACTIVE #type:ignore
        sub.save() #type:ignore

        for _ in range(3):
            AppointmentService.create_walk_in(
                clinic=self.clinic, patient=self.patient, doctor=self.doctor,
                appointment_type=self.appt_type, created_by=self.doctor.user,
            )

        today = timezone.localdate()
        invoice = InvoiceService.generate_monthly_invoice(
            self.clinic, today.replace(day=1), today
        )

        self.assertEqual(invoice.amount_due, Decimal("150.00")) #type:ignore
        self.assertEqual(VisitRecord.objects.filter(invoice=invoice).count(), 3)

    def test_pay_per_visit_with_no_visits_generates_no_invoice(self):
        sub = SubscriptionService.get_subscription(self.clinic)
        sub.plan = Subscription.Plan.PAY_PER_VISIT #type:ignore
        sub.status = Subscription.Status.ACTIVE #type:ignore
        sub.save() #type:ignore

        invoice = InvoiceService.generate_monthly_invoice(
            self.clinic, date(2025, 1, 1), date(2025, 1, 31)
        )

        self.assertIsNone(invoice)

    def test_visits_are_not_double_billed_across_invoice_runs(self):
        sub = SubscriptionService.get_subscription(self.clinic)
        sub.plan = Subscription.Plan.PAY_PER_VISIT #type:ignore
        sub.status = Subscription.Status.ACTIVE #type:ignore
        sub.save() #type:ignore

        AppointmentService.create_walk_in(
            clinic=self.clinic, patient=self.patient, doctor=self.doctor,
            appointment_type=self.appt_type, created_by=self.doctor.user,
        )

        today = timezone.localdate()
        first_invoice = InvoiceService.generate_monthly_invoice(self.clinic, today.replace(day=1), today)
        self.assertEqual(first_invoice.amount_due, Decimal("50.00")) #type:ignore

        # Running it again for the same period should find nothing left unbilled.
        second_invoice = InvoiceService.generate_monthly_invoice(self.clinic, today.replace(day=1), today)
        self.assertIsNone(second_invoice)


class ChargilyWebhookTests(TestCase):

    def setUp(self):
        self.specialty = Specialty.objects.create(name="General Medicine")
        self.clinic, self.doctor = ClinicService.create_clinic(
            clinic_name="Test Clinic", doctor_email="d@example.com", password="pw",
            first_name="J", last_name="D", specialty=self.specialty,
        )
        self.invoice = Invoice.objects.create(
            clinic=self.clinic, plan="standard",
            period_start=date(2025, 1, 1), period_end=date(2025, 1, 31),
            amount_due=Decimal("10000.00"), status=Invoice.Status.ISSUED,
            chargily_checkout_id="chk_test_123",
        )

    def test_webhook_rejects_invalid_signature(self):
        response = self.client.post(
            "/billing/webhook/",
            data=b'{"type": "checkout.paid", "data": {"id": "chk_test_123"}}',
            content_type="application/json",
            HTTP_SIGNATURE="not-a-real-signature",
        )
        self.assertEqual(response.status_code, 400)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.ISSUED)

    def test_webhook_marks_invoice_paid_with_valid_signature(self):
        import hmac, hashlib
        from django.conf import settings

        body = b'{"type": "checkout.paid", "data": {"id": "chk_test_123"}}'
        signature = hmac.new(settings.CHARGILY_SECRET.encode(), body, hashlib.sha256).hexdigest()

        response = self.client.post(
            "/billing/webhook/",
            data=body,
            content_type="application/json",
            HTTP_SIGNATURE=signature,
        )
        self.assertEqual(response.status_code, 200)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        self.assertIsNotNone(self.invoice.paid_at)



class PlanChangeRequestTests(TestCase):

    def setUp(self):
        self.specialty = Specialty.objects.create(name="General Medicine")
        self.clinic, self.doctor = ClinicService.create_clinic(
            clinic_name="Test Clinic", doctor_email="admin@example.com", password="StrongPassword123!",
            first_name="J", last_name="D", specialty=self.specialty,
        )

    def _fake_proof(self):
        return SimpleUploadedFile("proof.pdf", b"%PDF-1.4 fake proof content", content_type="application/pdf")

    def test_clinic_admin_can_submit_request(self):
        self.client.login(email="admin@example.com", password="StrongPassword123!")

        response = self.client.post(reverse("billing:request_plan_change"), {
            "requested_plan": "standard",
            "payment_method": "ccp",
            "proof_file": self._fake_proof(),
            "reference_note": "REF123",
        })

        self.assertRedirects(response, reverse("billing:status"))

        req = PlanChangeRequest.objects.get(clinic=self.clinic)
        self.assertEqual(req.status, PlanChangeRequest.Status.PENDING)
        self.assertEqual(req.requested_plan, "standard")
        self.assertTrue(req.proof_file)

    def test_non_admin_cannot_submit_request(self):
        from accounts.models import User
        from clinics.profiles import DoctorProfile

        regular_user = User.objects.create_doctor( #type:ignore
            email="regular@example.com", password="StrongPassword123!", clinic=self.clinic,
        )
        DoctorProfile.objects.create(user=regular_user, clinic=self.clinic, specialty=self.specialty)

        self.client.login(email="regular@example.com", password="StrongPassword123!")

        response = self.client.get(reverse("billing:request_plan_change"))

        self.assertEqual(response.status_code, 403)

    def test_approve_request_activates_plan(self):
        req = PlanRequestService.create_request(
            clinic=self.clinic, requested_by=self.doctor.user,
            requested_plan="standard", payment_method="bank_transfer",
            proof_file=self._fake_proof(),
        )

        superuser_email = "super@platform.com"
        from accounts.models import User
        superuser = User.objects.create_superuser(email=superuser_email, password="pw") #type:ignore

        PlanRequestService.approve(request_obj=req, reviewed_by=superuser)

        req.refresh_from_db()
        self.assertEqual(req.status, PlanChangeRequest.Status.APPROVED)
        self.assertEqual(req.reviewed_by, superuser)
        self.assertIsNotNone(req.reviewed_at)

        sub = SubscriptionService.get_subscription(self.clinic)
        self.assertEqual(sub.plan, Subscription.Plan.STANDARD) #type:ignore
        self.assertEqual(sub.status, Subscription.Status.ACTIVE) #type:ignore
        self.assertIsNone(sub.trial_ends_at) #type:ignore

    def test_reject_request_does_not_change_plan(self):
        req = PlanRequestService.create_request(
            clinic=self.clinic, requested_by=self.doctor.user,
            requested_plan="pay_per_visit", payment_method="ccp",
            proof_file=self._fake_proof(),
        )

        from accounts.models import User
        superuser = User.objects.create_superuser(email="super@platform.com", password="pw") #type:ignore

        PlanRequestService.reject(request_obj=req, reviewed_by=superuser, reason="Proof unreadable")

        req.refresh_from_db()
        self.assertEqual(req.status, PlanChangeRequest.Status.REJECTED)
        self.assertEqual(req.rejection_reason, "Proof unreadable")

        sub = SubscriptionService.get_subscription(self.clinic)
        self.assertEqual(sub.plan, Subscription.Plan.TRIAL)  # unchanged #type:ignore



class PaymentInstructionsTests(TestCase):

    def test_load_creates_singleton_on_first_access(self):
        self.assertEqual(PaymentInstructions.objects.count(), 0)

        instance = PaymentInstructions.load()

        self.assertEqual(instance.pk, 1)
        self.assertEqual(PaymentInstructions.objects.count(), 1)

    def test_load_returns_same_instance_on_repeated_calls(self):
        first = PaymentInstructions.load()
        first.bank_name = "Banque Test"
        first.save()

        second = PaymentInstructions.load()

        self.assertEqual(second.pk, first.pk)
        self.assertEqual(second.bank_name, "Banque Test")
        self.assertEqual(PaymentInstructions.objects.count(), 1)

    def test_get_returns_the_instance(self):
        instance = PaymentInstructions.load()
        instance.bank_name = "Banque Test"
        instance.save()

        result = PaymentInstructionsService.get()
        self.assertEqual(result.bank_name, "Banque Test")

    def test_request_form_shows_configured_instructions(self):
        specialty = Specialty.objects.create(name="General Medicine")
        clinic, doctor = ClinicService.create_clinic(
            clinic_name="Test Clinic", doctor_email="admin@example.com", password="StrongPassword123!",
            first_name="J", last_name="D", specialty=specialty,
        )

        instructions = PaymentInstructions.load()
        instructions.bank_name = "Banque Test"
        instructions.bank_rib = "1234567890"
        instructions.save()

        self.client.login(email="admin@example.com", password="StrongPassword123!")
        response = self.client.get(reverse("billing:request_plan_change"))

        self.assertContains(response, "Banque Test")
        self.assertContains(response, "1234567890")

    def test_request_form_shows_not_configured_warning_when_defaults(self):
        specialty = Specialty.objects.create(name="General Medicine")
        clinic, doctor = ClinicService.create_clinic(
            clinic_name="Test Clinic", doctor_email="admin2@example.com", password="StrongPassword123!",
            first_name="J", last_name="D", specialty=specialty,
        )

        self.client.login(email="admin2@example.com", password="StrongPassword123!")
        response = self.client.get(reverse("billing:request_plan_change"))

        # Instructions row exists (auto-created) but every field is blank
        self.assertEqual(response.status_code, 200)

class PlanChangeRequestFileValidationTests(TestCase):

    def setUp(self):
        self.specialty = Specialty.objects.create(name="General Medicine")
        self.clinic, self.doctor = ClinicService.create_clinic(
            clinic_name="Test Clinic", doctor_email="admin@example.com", password="StrongPassword123!",
            first_name="J", last_name="D", specialty=self.specialty,
        )

    def test_rejects_disallowed_file_extension(self):
        self.client.login(email="admin@example.com", password="StrongPassword123!")

        bad_file = SimpleUploadedFile("proof.exe", b"fake exe content", content_type="application/octet-stream")

        response = self.client.post(reverse("billing:request_plan_change"), {
            "requested_plan": "standard",
            "payment_method": "ccp",
            "proof_file": bad_file,
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())

    def test_rejects_oversized_file(self):
        self.client.login(email="admin@example.com", password="StrongPassword123!")

        oversized_content = b"x" * (6 * 1024 * 1024)  # 6MB — over the 5MB limit
        big_file = SimpleUploadedFile("proof.pdf", oversized_content, content_type="application/pdf")

        response = self.client.post(reverse("billing:request_plan_change"), {
            "requested_plan": "standard",
            "payment_method": "ccp",
            "proof_file": big_file,
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())

    def test_accepts_valid_pdf_under_size_limit(self):
        self.client.login(email="admin@example.com", password="StrongPassword123!")

        small_file = SimpleUploadedFile("proof.pdf", b"%PDF-1.4 small valid content", content_type="application/pdf")

        response = self.client.post(reverse("billing:request_plan_change"), {
            "requested_plan": "standard",
            "payment_method": "ccp",
            "proof_file": small_file,
        })

        self.assertRedirects(response, reverse("billing:status"))


class PlanChangeCheckoutTests(TestCase):

    def setUp(self):
        self.specialty = Specialty.objects.create(name="General Medicine")
        self.clinic, self.doctor = ClinicService.create_clinic(
            clinic_name="Test Clinic", doctor_email="admin@example.com", password="StrongPassword123!",
            first_name="J", last_name="D", specialty=self.specialty,
        )

    def test_switching_to_pay_per_visit_is_immediate_no_payment(self):
        self.client.login(email="admin@example.com", password="StrongPassword123!")

        response = self.client.post(reverse("billing:select_plan"), {"plan": "pay_per_visit"})

        self.assertRedirects(response, reverse("billing:status"))

        sub = SubscriptionService.get_subscription(self.clinic)
        self.assertEqual(sub.plan, Subscription.Plan.PAY_PER_VISIT) #type:ignore
        self.assertEqual(sub.status, Subscription.Status.ACTIVE) #type:ignore

        self.assertEqual(PlanChangeCheckout.objects.count(), 0)

    def test_switching_to_standard_creates_pending_checkout(self):
        with patch("billing.chargily.ChargilyService._create_checkout_session") as mock_session:
            mock_session.return_value = ("chk_test_abc", "https://pay.chargily.net/test/checkout/chk_test_abc")

            self.client.login(email="admin@example.com", password="StrongPassword123!")

            response = self.client.post(reverse("billing:select_plan"), {"plan": "standard"})

        self.assertRedirects(
            response, "https://pay.chargily.net/test/checkout/chk_test_abc", fetch_redirect_response=False
        )

        checkout = PlanChangeCheckout.objects.get(clinic=self.clinic)
        self.assertEqual(checkout.target_plan, "standard")
        self.assertEqual(checkout.amount, Decimal("10000.00"))
        self.assertEqual(checkout.status, PlanChangeCheckout.Status.PENDING)

        # Plan should NOT have switched yet — only the webhook confirms payment
        sub = SubscriptionService.get_subscription(self.clinic)
        self.assertEqual(sub.plan, Subscription.Plan.TRIAL) #type:ignore

    def test_webhook_completes_pending_plan_change_checkout(self):
        checkout = PlanChangeCheckoutService.create_pending(
            clinic=self.clinic, requested_by=self.doctor.user,
            target_plan="standard", amount=Decimal("10000.00"),
        )
        checkout.chargily_checkout_id = "chk_test_xyz"
        checkout.save()

        import hmac, hashlib, json
        from django.conf import settings

        body = json.dumps({"type": "checkout.paid", "data": {"id": "chk_test_xyz"}}).encode()
        signature = hmac.new(settings.CHARGILY_SECRET.encode(), body, hashlib.sha256).hexdigest()

        response = self.client.post(
            "/billing/webhook/", data=body, content_type="application/json", HTTP_SIGNATURE=signature,
        )
        self.assertEqual(response.status_code, 200)

        checkout.refresh_from_db()
        self.assertEqual(checkout.status, PlanChangeCheckout.Status.COMPLETED)
        self.assertIsNotNone(checkout.completed_at)

        sub = SubscriptionService.get_subscription(self.clinic)
        self.assertEqual(sub.plan, Subscription.Plan.STANDARD) #type:ignore
        self.assertEqual(sub.status, Subscription.Status.ACTIVE) #type:ignore

    def test_invalid_plan_value_rejected(self):
        self.client.login(email="admin@example.com", password="StrongPassword123!")

        response = self.client.post(reverse("billing:select_plan"), {"plan": "not_a_real_plan"})

        self.assertRedirects(response, reverse("billing:change_plan"))
        self.assertEqual(PlanChangeCheckout.objects.count(), 0)



class GenerateMonthlyInvoicesTaskTests(TestCase):

    def setUp(self):
        self.specialty = Specialty.objects.create(name="General Medicine")
        self.clinic, self.doctor = ClinicService.create_clinic(
            clinic_name="Test Clinic", doctor_email="admin@example.com", password="StrongPassword123!",
            first_name="J", last_name="D", specialty=self.specialty,
        )
        sub = SubscriptionService.get_subscription(self.clinic)
        sub.plan = Subscription.Plan.STANDARD #type:ignore
        sub.status = Subscription.Status.ACTIVE #type:ignore
        sub.save() #type:ignore
 
    def test_task_generates_invoice_for_active_standard_clinic(self):
        with patch("billing.chargily.ChargilyService._create_checkout_session") as mock_session:
            mock_session.return_value = ("chk_test", "https://pay.chargily.net/test/checkout/chk_test")

            result = generate_monthly_invoices()

        self.assertEqual(len(result["created"]), 1)
        self.assertEqual(result["created"][0]["clinic"], "Test Clinic")

    def test_task_skips_trial_clinics(self):
        # Reset to trial for this test
        sub = SubscriptionService.get_subscription(self.clinic)
        sub.plan = Subscription.Plan.TRIAL #type:ignore
        sub.status = Subscription.Status.TRIALING #type:ignore
        sub.save() #type:ignore

        result = generate_monthly_invoices()

        self.assertEqual(len(result["created"]), 0)

    def test_management_command_calls_task_and_reports_output(self):
        from io import StringIO
        from django.core.management import call_command

        with patch("billing.chargily.ChargilyService._create_checkout_session") as mock_session:
            mock_session.return_value = ("chk_test", "https://pay.chargily.net/test/checkout/chk_test")

            out = StringIO()
            call_command("generate_invoices", stdout=out)

        self.assertIn("Generated 1 invoice", out.getvalue())

    