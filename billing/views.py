from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils.translation import gettext as _ 

from .chargily import ChargilyService
from .services import (
    SubscriptionService, InvoiceService, PlanRequestService,
    PaymentInstructionsService, PlanChangeCheckoutService,
)
from .models import Subscription, Invoice

from .forms import PlanChangeRequestForm


# Create your views here.


def _require_clinic_admin(request):
    clinic = request.user.clinic

    if clinic is None or not request.user.is_clinic_admin:
        raise PermissionDenied(_("Only a clinic administrator can view billing."))

    return clinic

@login_required
def subscription_status(request):
    clinic = _require_clinic_admin(request)

    subscription = SubscriptionService.get_subscription(clinic)
    invoices = InvoiceService.get_for_clinic(clinic)
    trial_expired = SubscriptionService.is_trial_expired(clinic)
    plan_requests = PlanRequestService.get_for_clinic(clinic)

    context = {
        "subscription": subscription,
        "invoices": invoices,
        "trial_expired": trial_expired,
        "plan_requests": plan_requests,
    }
    return render(request, "billing/subscription.html", context)

@login_required
def pay_invoice(request, pk):
    clinic = _require_clinic_admin(request)

    invoice = get_object_or_404(Invoice, pk=pk, clinic=clinic)

    if not invoice.chargily_checkout_url:
        ChargilyService.create_checkout(invoice)
        invoice.refresh_from_db()

    return redirect(invoice.chargily_checkout_url)


def payment_success(request):
    return render(request, "billing/payment_success.html")


def payment_failure(request):
    return render(request, "billing/payment_failure.html")


@csrf_exempt
@require_POST
def chargily_webhook(request):
    signature = request.META.get("HTTP_SIGNATURE", "")

    if not ChargilyService.verify_webhook_signature(request.body, signature):
        return HttpResponseBadRequest("Invalid signature")

    import json
    try:
        event = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest("Invalid JSON")

    ChargilyService.handle_webhook_event(event)

    return HttpResponse(status=200)


@login_required
def change_plan(request):
    clinic = _require_clinic_admin(request)

    subscription = SubscriptionService.get_subscription(clinic)

    plans = [
        {
            "value": Subscription.Plan.STANDARD,
            "label": _("Standard"),
            "price": SubscriptionService.get_plan_price(Subscription.Plan.STANDARD),
            "description": _("1 doctor + 1 secretary, unlimited patients."),
            "requires_payment": True,
        },
        {
            "value": Subscription.Plan.PAY_PER_VISIT,
            "label": _("Pay per visit"),
            "price": None,
            "description": _("Unlimited staff and patients. 50 DA per visit, billed monthly based on actual usage."),
            "requires_payment": False,
        },
    ]

    context = {"subscription": subscription, "plans": plans}
    return render(request, "billing/change_plan.html", context)


@login_required
@require_POST
def select_plan(request):
    clinic = _require_clinic_admin(request)

    target_plan = request.POST.get("plan")

    if target_plan not in (Subscription.Plan.STANDARD, Subscription.Plan.PAY_PER_VISIT):
        messages.error(request, _("Invalid plan selection."))
        return redirect("billing:change_plan")

    price = SubscriptionService.get_plan_price(target_plan)

    if price is None:
        # Pay-per-visit — no payment needed, switch takes effect immediately.
        SubscriptionService.switch_plan(clinic, target_plan)
        messages.success(request, _("Your plan has been switched to Pay-per-visit."))
        return redirect("billing:status")

    # Standard — needs payment first; create a Chargily checkout and send them there.
    checkout = PlanChangeCheckoutService.create_pending(
        clinic=clinic, requested_by=request.user, target_plan=target_plan, amount=price,
    )
    ChargilyService.create_plan_change_checkout(checkout)

    return redirect(checkout.chargily_checkout_url)

@login_required
def request_plan_change(request):
    clinic = _require_clinic_admin(request)

    if request.method == "POST":
        form = PlanChangeRequestForm(request.POST, request.FILES)

        if form.is_valid():
            PlanRequestService.create_request(
                clinic=clinic,
                requested_by=request.user,
                requested_plan=form.cleaned_data["requested_plan"],
                payment_method=form.cleaned_data["payment_method"],
                proof_file=form.cleaned_data["proof_file"],
                reference_note=form.cleaned_data["reference_note"],
            )

            messages.success(
                request,
                _("Your request has been submitted. We'll review your proof of payment and activate your plan shortly.")
            )
            return redirect("billing:status")

    else:
        form = PlanChangeRequestForm()

    context = {
        "form": form,
        "payment_instructions": PaymentInstructionsService.get(),
    }
    return render(request, "billing/request_plan_change.html", context)



