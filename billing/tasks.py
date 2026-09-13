from datetime import date
from calendar import monthrange

from celery import shared_task

from .chargily import ChargilyService
from .models import Subscription
from .services import InvoiceService


@shared_task
def generate_monthly_invoices():
    """
    Celery task version of the generate_invoices management command's
    logic — same behavior, callable on a schedule instead of only by hand.
    Returns a summary dict rather than printing, since there's no terminal
    to print to when this runs unattended.
    """
    today = date.today()

    if today.month == 1:
        period_start = date(today.year - 1, 12, 1)
    else:
        period_start = date(today.year, today.month - 1, 1)
    period_end = date(period_start.year, period_start.month, monthrange(period_start.year, period_start.month)[1])

    subscriptions = Subscription.objects.filter(
        plan__in=[Subscription.Plan.STANDARD, Subscription.Plan.PAY_PER_VISIT],
        status=Subscription.Status.ACTIVE,
    ).select_related("clinic")

    created = []
    failed = []

    for sub in subscriptions:
        invoice = InvoiceService.generate_monthly_invoice(sub.clinic, period_start, period_end)

        if invoice is None:
            continue

        try:
            ChargilyService.create_checkout(invoice)
        except Exception as e:
            failed.append({"invoice_id": invoice.pk, "clinic": sub.clinic.name, "error": str(e)})
            continue

        created.append({"invoice_id": invoice.pk, "clinic": sub.clinic.name, "amount": str(invoice.amount_due)})

    return {
        "period_start": str(period_start),
        "period_end": str(period_end),
        "created": created,
        "failed": failed,
    }