from django.core.management.base import BaseCommand

from billing.tasks import generate_monthly_invoices


class Command(BaseCommand):
    help = "Generates monthly invoices for all clinics on paid plans, and creates Chargily checkouts for them. Runs synchronously (not via Celery) when invoked manually."

    def handle(self, *args, **options):
        result = generate_monthly_invoices()

        for entry in result["created"]:
            self.stdout.write(f"Invoice #{entry['invoice_id']} for {entry['clinic']}: {entry['amount']} DA")

        for entry in result["failed"]:
            self.stderr.write(f"Failed for {entry['clinic']}: {entry['error']}")

        self.stdout.write(self.style.SUCCESS(
            f"Generated {len(result['created'])} invoice(s), {len(result['failed'])} failure(s) "
            f"for {result['period_start']} – {result['period_end']}."
        ))