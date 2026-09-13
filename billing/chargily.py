import hashlib
import hmac

import requests
from django.conf import settings

class ChargilyService:

    @staticmethod
    def _create_checkout_session(*, amount, description):
        """
        Low-level call to Chargily's checkout endpoint. Returns the raw
        (checkout_id, checkout_url) pair — callers are responsible for
        persisting those onto whatever local record they represent
        (Invoice or PlanChangeCheckout).
        """
        response = requests.post(
            f"{settings.CHARGILY_BASE_URL}checkouts",
            headers={
                "Authorization": f"Bearer {settings.CHARGILY_SECRET}",
                "Content-Type": "application/json",
            },
            json={
                "amount": float(amount),
                "currency": "dzd",
                "success_url": settings.CHARGILY_SUCCESS_URL,
                "failure_url": settings.CHARGILY_FAILURE_URL,
                "webhook_endpoint": settings.CHARGILY_WEBHOOK_URL,
                "description": description,
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        return data["id"], data["checkout_url"]

    @staticmethod
    def create_checkout(invoice):
        """Creates a Chargily checkout for a recurring/usage Invoice."""
        checkout_id, checkout_url = ChargilyService._create_checkout_session(
            amount=invoice.amount_due,
            description=f"MediCore invoice #{invoice.pk} — {invoice.clinic.name}",
        )

        invoice.chargily_checkout_id = checkout_id
        invoice.chargily_checkout_url = checkout_url
        invoice.status = invoice.__class__.Status.ISSUED
        invoice.save(update_fields=["chargily_checkout_id", "chargily_checkout_url", "status"])

        return invoice

    @staticmethod
    def create_plan_change_checkout(checkout):
        """Creates a Chargily checkout for a self-serve plan switch."""
        checkout_id, checkout_url = ChargilyService._create_checkout_session(
            amount=checkout.amount,
            description=f"MediCore plan switch to {checkout.get_target_plan_display()} — {checkout.clinic.name}",
        )

        checkout.chargily_checkout_id = checkout_id
        checkout.chargily_checkout_url = checkout_url
        checkout.save(update_fields=["chargily_checkout_id", "chargily_checkout_url"])

        return checkout
    @staticmethod
    def verify_webhook_signature(raw_body: bytes, signature_header: str) -> bool:
        """
        HMAC-SHA256 of the raw request body, keyed with the Chargily secret,
        compared against the 'signature' header — following the pattern used
        by Chargily's own JS/Python SDKs.

        IMPORTANT: verify this exact scheme against Chargily's dashboard/API
        reference before relying on it in production — this was reconstructed
        from their SDK repos, not confirmed against their canonical spec page.
        """
        if not signature_header:
            return False

        expected = hmac.new(
            settings.CHARGILY_SECRET.encode(), raw_body, hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, signature_header)


    @staticmethod
    def handle_webhook_event(event: dict):
        from django.utils import timezone
        from .models import Invoice, PlanChangeCheckout
        from .services import PlanChangeCheckoutService

        event_type = event.get("type", "")
        checkout_id = event.get("data", {}).get("id")

        if not checkout_id:
            return None

        if event_type == "checkout.paid":
            invoice = Invoice.objects.filter(chargily_checkout_id=checkout_id).first()
            if invoice:
                if invoice.status != Invoice.Status.PAID:
                    invoice.status = Invoice.Status.PAID
                    invoice.paid_at = timezone.now()
                    invoice.save(update_fields=["status", "paid_at"])
                return invoice

            plan_checkout = PlanChangeCheckout.objects.filter(chargily_checkout_id=checkout_id).first()
            if plan_checkout and plan_checkout.status != PlanChangeCheckout.Status.COMPLETED:
                PlanChangeCheckoutService.mark_completed(plan_checkout)
                return plan_checkout

            return None

        if event_type in ("checkout.failed", "checkout.expired"):
            invoice = Invoice.objects.filter(chargily_checkout_id=checkout_id).first()
            if invoice and invoice.status == Invoice.Status.ISSUED:
                invoice.status = Invoice.Status.OVERDUE
                invoice.save(update_fields=["status"])
                return invoice

            plan_checkout = PlanChangeCheckout.objects.filter(chargily_checkout_id=checkout_id).first()
            if plan_checkout and plan_checkout.status == PlanChangeCheckout.Status.PENDING:
                from .services import PlanChangeCheckoutService as PCS
                PCS.mark_failed(plan_checkout)
                return plan_checkout

            return None

        return None