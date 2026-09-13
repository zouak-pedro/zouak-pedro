from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from appointments.services import AppointmentService

from records.services import (
    PrescriptionService, DoctorNoteService, ProcedureReportService, LabworkDemandService,
)
from records.forms import (
    PrescriptionForm, PrescriptionItemFormSet, DoctorNoteForm,
    ProcedureReportForm, ProcedureItemFormSet,
    LabworkDemandForm, LabworkItemFormSet,
)

from records.models import Prescription, DoctorNote, ProcedureReport, LabworkDemand

from .forms import PatientForm
from .services import PatientService
from .models import Patient

from django.utils import timezone
from django.utils.translation import gettext as _

# Create your views here.

def _require_clinic(request):
    """
    Guards against users with no clinic (e.g.) platform superusers with no clinic assigned
    hitting patient views. Returns the clinic or raises.
    """
    clinic = request.user.clinic

    if clinic is None:
        raise PermissionDenied(_(_("You must belong to a clinic to manage patients.")))

    return clinic


@login_required
def patient_list(request):
    clinic = _require_clinic(request)

    patients = PatientService.get_for_clinic(clinic)

    context = {"patients": patients}
    return render(request, "patients/list.html", context)

@login_required
def add_patient(request):
    clinic = _require_clinic(request)

    if request.method == "POST":
        form = PatientForm(request.POST)

        if form.is_valid():
            try:
                PatientService.create_patient(
                    clinic=clinic,
                    first_name=form.cleaned_data["first_name"],
                    last_name=form.cleaned_data["last_name"],
                    date_of_birth=form.cleaned_data["date_of_birth"],
                    approximate_age=form.cleaned_data["approximate_age"],
                    phone=form.cleaned_data["phone"],
                    address=form.cleaned_data["address"],
                    reason_for_visit=form.cleaned_data["reason_for_visit"],
                )
            except ValueError as e:
                form.add_error(None, str(e))
            else:
                messages.success(request, _("Patient added successfully"))
                return redirect("patients:list")

    else:
        form = PatientForm()

    context = {"form": form}
    return render(request, "patients/add.html", context)
def _get_patient_or_404(clinic, patient_id):
    return get_object_or_404(Patient.objects.for_clinic(clinic), pk=patient_id) #type:ignore

@login_required
def patient_detail(request, pk):
    clinic = _require_clinic(request)

    patient = _get_patient_or_404(clinic, pk)

    filters = {
        prefix: {
            "search": request.GET.get(f"{prefix}_search", ""),
            "start": request.GET.get(f"{prefix}_start", ""),
            "end": request.GET.get(f"{prefix}_end", ""),
        }
        for prefix in ("appt", "rx", "note", "proc", "lab")
    }

    context = {
        "patient": patient,
        "appointments": AppointmentService.get_for_patient(
            clinic, patient,
            search=filters["appt"]["search"] or None,
            start_date=filters["appt"]["start"] or None,
            end_date=filters["appt"]["end"] or None,
        ),
        "prescriptions": PrescriptionService.get_for_patient(
            clinic, patient,
            search=filters["rx"]["search"] or None,
            start_date=filters["rx"]["start"] or None,
            end_date=filters["rx"]["end"] or None,
        ),
        "notes": DoctorNoteService.get_for_patient(
            clinic, patient,
            search=filters["note"]["search"] or None,
            start_date=filters["note"]["start"] or None,
            end_date=filters["note"]["end"] or None,
        ),
        "procedure_reports": ProcedureReportService.get_for_patient(
            clinic, patient,
            search=filters["proc"]["search"] or None,
            start_date=filters["proc"]["start"] or None,
            end_date=filters["proc"]["end"] or None,
        ),
        "labwork_demands": LabworkDemandService.get_for_patient(
            clinic, patient,
            search=filters["lab"]["search"] or None,
            start_date=filters["lab"]["start"] or None,
            end_date=filters["lab"]["end"] or None,
        ),
        "filters": filters,
        "today": timezone.localdate().isoformat(),
    }
    return render(request, "patients/detail.html", context)




@login_required
def edit_patient(request, pk):
    clinic = _require_clinic(request)

    patient = get_object_or_404(Patient.objects.for_clinic(clinic), pk=pk) #type:ignore

    if request.method == "POST":
        form = PatientForm(request.POST)

        if form.is_valid():
            PatientService.update_patient(
                patient=patient,
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                date_of_birth=form.cleaned_data["date_of_birth"],
                approximate_age=form.cleaned_data["approximate_age"],
                phone=form.cleaned_data["phone"],
                address=form.cleaned_data["address"],
                reason_for_visit=form.cleaned_data["reason_for_visit"],
            )

            messages.success(request, "Patient updated")
            return redirect("patients:detail", pk=patient.pk)

    else:
        form = PatientForm(initial={
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "date_of_birth": patient.date_of_birth,
            "approximate_age": patient.approximate_age,
            "phone": patient.phone,
            "address": patient.address,
            "reason_for_visit": patient.reason_for_visit,
        })

    context = {"form": form, "patient": patient}
    return render(request, "patients/edit.html", context)



@login_required
def add_prescription(request, patient_id):
    clinic = _require_clinic(request)
    patient = _get_patient_or_404(clinic, patient_id)

    if request.method == "POST":
        form = PrescriptionForm(request.POST, clinic=clinic)
        formset = PrescriptionItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            items = [
                {
                    "medication_name": f.cleaned_data["medication_name"],
                    "dosage": f.cleaned_data["dosage"],
                    "frequency": f.cleaned_data["frequency"],
                    "duration": f.cleaned_data["duration"],
                    "instructions": f.cleaned_data["instructions"],
                }
                for f in formset
                if f.cleaned_data and not f.cleaned_data.get("DELETE") and f.cleaned_data.get("medication_name")
            ]

            prescription = PrescriptionService.create_prescription(
                clinic=clinic, patient=patient, doctor=form.cleaned_data["doctor"],
                notes=form.cleaned_data["notes"], items=items,
                patient_name_override=form.cleaned_data["patient_name_override"],
            )

            messages.success(request, _("Prescription created"))
            return redirect("records:prescription_print", pk=prescription.pk)

    else:
        form = PrescriptionForm(clinic=clinic)
        formset = PrescriptionItemFormSet()

    context = {"form": form, "formset": formset, "patient": patient}
    return render(request, "records/prescription_add.html", context)

@login_required
def edit_prescription(request, patient_id, pk):
    clinic = _require_clinic(request)
    patient = _get_patient_or_404(clinic, patient_id)
    prescription = get_object_or_404(
        Prescription.objects.for_clinic(clinic).filter(patient=patient).prefetch_related("items"), pk=pk #type:ignore
    )

    if request.method == "POST":
        form = PrescriptionForm(request.POST, clinic=clinic)
        formset = PrescriptionItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            items = [
                {
                    "medication_name": f.cleaned_data["medication_name"],
                    "dosage": f.cleaned_data["dosage"],
                    "frequency": f.cleaned_data["frequency"],
                    "duration": f.cleaned_data["duration"],
                    "instructions": f.cleaned_data["instructions"],
                }
                for f in formset
                if f.cleaned_data and not f.cleaned_data.get("DELETE") and f.cleaned_data.get("medication_name")
            ]

            try:
                PrescriptionService.update_prescription(
                    prescription=prescription, doctor=form.cleaned_data["doctor"],
                    notes=form.cleaned_data["notes"], items=items,
                    patient_name_override=form.cleaned_data["patient_name_override"],
                )
            except ValueError as e:
                form.add_error(None, str(e))
            else:
                messages.success(request, _("Prescription updated"))
                return redirect("records:prescription_print", pk=prescription.pk)

    else:
        form = PrescriptionForm(clinic=clinic, initial={
            "doctor": prescription.doctor_id, "notes": prescription.notes,
            "patient_name_override": prescription.patient_name_override,
        })
        formset = PrescriptionItemFormSet(initial=[
            {
                "medication_name": item.medication_name, "dosage": item.dosage,
                "frequency": item.frequency, "duration": item.duration,
                "instructions": item.instructions,
            }
            for item in prescription.items.all()
        ])
        formset.extra = max(formset.extra, len(prescription.items.all()) + 1)

    context = {"form": form, "formset": formset, "patient": patient, "prescription": prescription}
    return render(request, "records/prescription_edit.html", context)

@login_required
def add_note(request, patient_id):
    clinic = _require_clinic(request)
    patient = _get_patient_or_404(clinic, patient_id)

    if request.method == "POST":
        form = DoctorNoteForm(request.POST, clinic=clinic)

        if form.is_valid():
            note = DoctorNoteService.create_note(
                clinic=clinic, patient=patient, doctor=form.cleaned_data["doctor"],
                content=form.cleaned_data["content"],
            )

            messages.success(request, _("Note saved"))
            return redirect("records:note_print", pk=note.pk)

    else:
        form = DoctorNoteForm(clinic=clinic)

    context = {"form": form, "patient": patient}
    return render(request, "records/note_add.html", context)

@login_required
def edit_note(request, patient_id, pk):
    clinic = _require_clinic(request)
    patient = _get_patient_or_404(clinic, patient_id)
    note = get_object_or_404(DoctorNote.objects.for_clinic(clinic).filter(patient=patient), pk=pk) #type:ignore

    if request.method == "POST":
        form = DoctorNoteForm(request.POST, clinic=clinic)

        if form.is_valid():
            try:
                DoctorNoteService.update_note(
                    note=note, doctor=form.cleaned_data["doctor"], content=form.cleaned_data["content"],
                )
            except ValueError as e:
                form.add_error(None, str(e))
            else:
                messages.success(request, _("Note updated"))
                return redirect("records:note_print", pk=note.pk)

    else:
        form = DoctorNoteForm(clinic=clinic, initial={"doctor": note.doctor_id, "content": note.content})

    context = {"form": form, "patient": patient, "note": note}
    return render(request, "records/note_edit.html", context)


@login_required
def add_procedure_report(request, patient_id):
    clinic = _require_clinic(request)
    patient = _get_patient_or_404(clinic, patient_id)

    if request.method == "POST":
        form = ProcedureReportForm(request.POST, clinic=clinic)
        formset = ProcedureItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            items = [
                {"procedure_name": f.cleaned_data["procedure_name"], "findings": f.cleaned_data.get("findings", "")}
                for f in formset
                if f.cleaned_data and not f.cleaned_data.get("DELETE") and f.cleaned_data.get("procedure_name")
            ]

            report = ProcedureReportService.create_report(
                clinic=clinic, patient=patient, doctor=form.cleaned_data["doctor"],
                notes=form.cleaned_data["notes"], items=items,
            )

            messages.success(request, _("Procedure report created"))
            return redirect("records:procedure_report_print", pk=report.pk)

    else:
        form = ProcedureReportForm(clinic=clinic)
        formset = ProcedureItemFormSet()

    context = {"form": form, "formset": formset, "patient": patient}
    return render(request, "records/procedure_report_add.html", context)

@login_required
def edit_procedure_report(request, patient_id, pk):
    clinic = _require_clinic(request)
    patient = _get_patient_or_404(clinic, patient_id)
    report = get_object_or_404(
        ProcedureReport.objects.for_clinic(clinic).filter(patient=patient).prefetch_related("items"), pk=pk #type:ignore
    )

    if request.method == "POST":
        form = ProcedureReportForm(request.POST, clinic=clinic)
        formset = ProcedureItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            items = [
                {"procedure_name": f.cleaned_data["procedure_name"], "findings": f.cleaned_data.get("findings", "")}
                for f in formset
                if f.cleaned_data and not f.cleaned_data.get("DELETE") and f.cleaned_data.get("procedure_name")
            ]

            try:
                ProcedureReportService.update_report(
                    report=report, doctor=form.cleaned_data["doctor"],
                    notes=form.cleaned_data["notes"], items=items,
                )
            except ValueError as e:
                form.add_error(None, str(e))
            else:
                messages.success(request, _("Procedure report updated"))
                return redirect("records:procedure_report_print", pk=report.pk)

    else:
        form = ProcedureReportForm(clinic=clinic, initial={
            "doctor": report.doctor_id, "notes": report.notes,
        })
        formset = ProcedureItemFormSet(initial=[
            {"procedure_name": item.procedure_name, "findings": item.findings}
            for item in report.items.all()
        ])
        formset.extra = max(formset.extra, len(report.items.all()) + 1)

    context = {"form": form, "formset": formset, "patient": patient, "report": report}
    return render(request, "records/procedure_report_edit.html", context)


@login_required
def add_labwork_demand(request, patient_id):
    clinic = _require_clinic(request)
    patient = _get_patient_or_404(clinic, patient_id)

    if request.method == "POST":
        form = LabworkDemandForm(request.POST, clinic=clinic)
        formset = LabworkItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            items = [
                {
                    "test_name": f.cleaned_data["test_name"],
                    "urgency": f.cleaned_data["urgency"],
                    "clinical_indication": f.cleaned_data.get("clinical_indication", ""),
                }
                for f in formset
                if f.cleaned_data and not f.cleaned_data.get("DELETE") and f.cleaned_data.get("test_name")
            ]

            demand = LabworkDemandService.create_demand(
                clinic=clinic, patient=patient, doctor=form.cleaned_data["doctor"], items=items,
            )

            messages.success(request, _("Labwork demand created"))
            return redirect("records:labwork_demand_print", pk=demand.pk)

    else:
        form = LabworkDemandForm(clinic=clinic)
        formset = LabworkItemFormSet()

    context = {"form": form, "formset": formset, "patient": patient}
    return render(request, "records/labwork_demand_add.html", context)


@login_required
def edit_labwork_demand(request, patient_id, pk):
    clinic = _require_clinic(request)
    patient = _get_patient_or_404(clinic, patient_id)
    demand = get_object_or_404(
        LabworkDemand.objects.for_clinic(clinic).filter(patient=patient).prefetch_related("items"), pk=pk #type:ignore
    )

    if request.method == "POST":
        form = LabworkDemandForm(request.POST, clinic=clinic)
        formset = LabworkItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            items = [
                {
                    "test_name": f.cleaned_data["test_name"],
                    "urgency": f.cleaned_data["urgency"],
                    "clinical_indication": f.cleaned_data.get("clinical_indication", ""),
                }
                for f in formset
                if f.cleaned_data and not f.cleaned_data.get("DELETE") and f.cleaned_data.get("test_name")
            ]

            try:
                LabworkDemandService.update_demand(
                    demand=demand, doctor=form.cleaned_data["doctor"], items=items,
                )
            except ValueError as e:
                form.add_error(None, str(e))
            else:
                messages.success(request, _("Labwork demand updated"))
                return redirect("records:labwork_demand_print", pk=demand.pk)

    else:
        form = LabworkDemandForm(clinic=clinic, initial={"doctor": demand.doctor_id})
        formset = LabworkItemFormSet(initial=[
            {
                "test_name": item.test_name, "urgency": item.urgency,
                "clinical_indication": item.clinical_indication,
            }
            for item in demand.items.all()
        ])
        formset.extra = max(formset.extra, len(demand.items.all()) + 1)

    context = {"form": form, "formset": formset, "patient": patient, "demand": demand}
    return render(request, "records/labwork_demand_edit.html", context)



