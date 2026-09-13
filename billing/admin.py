from django.contrib import admin
from django.utils.html import format_html

from .models import Subscription, VisitRecord, Invoice, PlanChangeRequest, PaymentInstructions
from .services import PlanRequestService
# Register your models here.

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("clinic", "plan", "status", "trial_ends_at")
    list_filter = ("plan", "status")


@admin.register(VisitRecord)
class VisitRecordAdmin(admin.ModelAdmin):
    list_display = ("clinic", "appointment", "amount", "invoice", "created_at")
    list_filter = ("clinic",)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("clinic", "plan", "period_start", "period_end", "amount_due", "status")
    list_filter = ("plan", "status")


@admin.register(PlanChangeRequest)
class PlanChangeRequestAdmin(admin.ModelAdmin):
    list_display = (
        "clinic", "requested_plan", "payment_method", "status",
        "proof_link", "created_at", "reviewed_by",
    )
    list_filter = ("status", "requested_plan", "payment_method")
    search_fields = ("clinic__name", "reference_note")
    readonly_fields = ("clinic", "requested_by", "requested_plan", "payment_method",
                       "proof_file", "reference_note", "created_at")

    actions = ["approve_requests", "reject_requests"]

    def proof_link(self, obj):
        if obj.proof_file:
            return format_html('<a href="{}" target="_blank">View proof</a>', obj.proof_file.url)
        return "—"
    proof_link.short_description = "Proof of payment"

    @admin.action(description="Approve selected requests (activates the new plan)")
    def approve_requests(self, request, queryset):
        count = 0
        for req in queryset.filter(status=PlanChangeRequest.Status.PENDING):
            PlanRequestService.approve(request_obj=req, reviewed_by=request.user)
            count += 1
        self.message_user(request, f"Approved {count} request(s) and activated the corresponding plans.")

    @admin.action(description="Reject selected requests")
    def reject_requests(self, request, queryset):
        count = 0
        for req in queryset.filter(status=PlanChangeRequest.Status.PENDING):
            PlanRequestService.reject(request_obj=req, reviewed_by=request.user, reason="Rejected via admin bulk action")
            count += 1
        self.message_user(request, f"Rejected {count} request(s).")


@admin.register(PaymentInstructions)
class PaymentInstructionsAdmin(admin.ModelAdmin):
    fields = ("bank_name", "bank_rib", "ccp_number", "ccp_key", "additional_notes", "updated_at")
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return False  # never manually "add" — the singleton creates itself

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Skip the changelist entirely — ensure the row exists, then go straight to editing it.
        instance = PaymentInstructions.load()
        return redirect(reverse("admin:billing_paymentinstructions_change", args=[instance.pk])) #type:ignore