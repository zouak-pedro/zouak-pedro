from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from .forms import (
    PrescriptionForm, PrescriptionItemFormSet, DoctorNoteForm,
    ProcedureReportForm, ProcedureItemFormSet,
    LabworkDemandForm, LabworkItemFormSet,
    DoctorDocumentProfileForm,
)

from .services import (
    PrescriptionService, MedicationService, DoctorNoteService,
    ProcedureReportService, LabworkDemandService,
)
from .models import DoctorDocumentProfile, Prescription, DoctorNote, ProcedureReport, LabworkDemand

from django.http import JsonResponse

from accounts.models import User

from core.services import AuditLogService


# Create your views here.

@login_required
def medication_suggest(request):
    query = request.GET.get("q", "")
    medications = MedicationService.suggest(query)

    return JsonResponse({"results": [m.name for m in medications]})

def _require_clinic(request):
    clinic = request.user.clinic

    if clinic is None:
        raise PermissionDenied(_("You must belong to a clinic to manage medical records."))

    return clinic


@login_required
def prescription_print(request, pk):
    clinic = _require_clinic(request)

    prescription = get_object_or_404(
        Prescription.objects.for_clinic(clinic).select_related("patient", "doctor__user", "clinic"), #type:ignore
        pk=pk,
    )

    AuditLogService.log(
        actor=request.user, clinic=clinic, action=AuditLogService.Action.PRINT,
        target=prescription, path=request.path, method=request.method,
    )

    html_string = render_to_string("records/prescription_pdf.html", {
        "prescription": prescription,
        "clinic": clinic,
        "doctor": prescription.doctor,
        "items": prescription.items.all()

    })

    from weasyprint import HTML

    pdf_bytes = HTML(string=html_string).write_pdf()

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="prescription_{prescription.pk}.pdf'

    return response




@login_required
def note_print(request, pk):
    clinic = _require_clinic(request)

    note = get_object_or_404(
        DoctorNote.objects.for_clinic(clinic).select_related("patient", "doctor__user", "clinic"), #type:ignore
        pk=pk,
    )

    AuditLogService.log(
        actor=request.user, clinic=clinic, action=AuditLogService.Action.PRINT,
        target=note, path=request.path, method=request.method,
    )

    html_string = render_to_string("records/note_pdf.html", {
        "note": note,
        "clinic": clinic,
        "doctor": note.doctor,
    })

    from weasyprint import HTML

    pdf_bytes = HTML(string=html_string).write_pdf()

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="note_{note.pk}.pdf"'
    return response






@login_required
def procedure_report_print(request, pk):
    clinic = _require_clinic(request)

    report = get_object_or_404(
        ProcedureReport.objects.for_clinic(clinic).select_related("patient", "doctor__user", "clinic"), #type:ignore
        pk=pk,
    ) 

    AuditLogService.log(
        actor=request.user, clinic=clinic, action=AuditLogService.Action.PRINT,
        target=report, path=request.path, method=request.method,
    )

    html_string = render_to_string("records/procedure_report_pdf.html", {
        "report": report, "clinic": clinic, "doctor": report.doctor, "items": report.items.all(),
    })

    from weasyprint import HTML
    pdf_bytes = HTML(string=html_string).write_pdf()

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="procedure_report_{report.pk}.pdf"'
    return response




@login_required
def labwork_demand_print(request, pk):
    clinic = _require_clinic(request)

    demand = get_object_or_404(
        LabworkDemand.objects.for_clinic(clinic).select_related("patient", "doctor__user", "clinic"), #type:ignore
        pk=pk,
    )

    AuditLogService.log(
        actor=request.user, clinic=clinic, action=AuditLogService.Action.PRINT,
        target=demand, path=request.path, method=request.method,
    )

    html_string = render_to_string("records/labwork_demand_pdf.html", {
        "demand": demand, "clinic": clinic, "doctor": demand.doctor, "items": demand.items.all(),
    })

    from weasyprint import HTML
    pdf_bytes = HTML(string=html_string).write_pdf()

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="labwork_demand_{demand.pk}.pdf"'
    return response


@login_required
def edit_document_profile(request):
    if request.user.role != User.Role.DOCTOR:
        raise PermissionDenied(_("Only doctors have a document profile.")) 

    doctor = getattr(request.user, "doctor_profile", None)
    if doctor is None:
        raise PermissionDenied(_("Your account has no doctor profile."))

    document_profile, __ = DoctorDocumentProfile.objects.get_or_create(doctor=doctor)

    if request.method == "POST":
        form = DoctorDocumentProfileForm(request.POST, request.FILES, instance=document_profile)

        if form.is_valid():
            form.save()
            messages.success(request, _("Document profile updated"))
            return redirect("records:edit_document_profile")

    else: 
        form = DoctorDocumentProfileForm(instance=document_profile) 

    context = {"form": form}
    return render(request, "records/document_profile.html", context)