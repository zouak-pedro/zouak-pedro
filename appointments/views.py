from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from .forms import AppointmentForm, WalkInForm, AppointmentTypeService, AppointmentEditForm
from .services import AppointmentService
from .models import Appointment

# Create your views here.

@login_required
def appointment_type_suggest(request):
    query = request.GET.get("q", "")
    types = AppointmentTypeService.suggest(query)

    return JsonResponse({"results": [t.name for t in types]})

def _require_clinic(request):
    clinic = request.user.clinic

    if clinic is None:
        raise PermissionDenied(_("You must belong to a clinic to manage appointments."))

    return clinic

@login_required
def day_view(request, date=None):
    clinic = _require_clinic(request)

    day = parse_date(date) if date else None
    if day is None:
        day = timezone.localdate()

    appointments = AppointmentService.get_for_day(clinic, day)

    context = {
        "appointments": appointments,
        "day": day
    }

    return render(request, "appointments/day_list.html", context)


@login_required
def add_appointment(request):
    clinic = _require_clinic(request)

    if request.method == "POST":
        form = AppointmentForm(request.POST, clinic=clinic)
        next_url = request.POST.get("next")

        if form.is_valid():
            AppointmentService.create_appointment(
                clinic=clinic,
                patient=form.cleaned_data['patient'],
                doctor=form.cleaned_data['doctor'],
                appointment_type=form.cleaned_data["type"],
                scheduled_at=form.cleaned_data['scheduled_at'],
                created_by=request.user,
            )

            messages.success(request, _("Appointment booked successfully"))

            return redirect(next_url or "appointments:day")

    else:
        initial = {}
        patient_id = request.GET.get("patient")
        if patient_id:
            initial["patient"] = patient_id

        form = AppointmentForm(clinic=clinic, initial=initial)

    context = {"form": form, "next_url": request.GET.get("next", "")}
    return render(request, "appointments/add.html", context)


@login_required
def add_walk_in(request):
    clinic = _require_clinic(request)

    if request.method == 'POST':
        form = WalkInForm(request.POST, clinic=clinic)
        next_url = request.POST.get("next")

        if form.is_valid():
            AppointmentService.create_walk_in(
                clinic=clinic,
                patient=form.cleaned_data['patient'],
                doctor=form.cleaned_data['doctor'],
                appointment_type=form.cleaned_data["type"],
                created_by=request.user,
            )

            messages.success(request, _("Walk-in added to today's list"))

            return redirect(next_url or "appointments:day")

    else: 
        initial = {}
        patient_id = request.GET.get("patient")
        if patient_id:
            initial["patient"] = patient_id

        form = WalkInForm(clinic=clinic, initial=initial)

    context = {"form": form, "next_url": request.GET.get("next", "")}
    return render(request, "appointments/walk_in.html", context)


@login_required
@require_POST
def update_status(request, pk):
    clinic = _require_clinic(request)

    appointment = get_object_or_404(Appointment.objects.for_clinic(clinic), pk=pk) #type:ignore

    new_status = request.POST.get("status")

    try:
        AppointmentService.update_status(appointment=appointment, new_status=new_status)
    except ValueError:
        messages.error(request, _("Invalid status."))
    else:
        messages.success(request, _("Status updated"))

    return redirect("appointments:day")


@login_required
def edit_appointment(request, pk):
    clinic = _require_clinic(request)

    appointment = get_object_or_404(Appointment.objects.for_clinic(clinic).select_related("patient"), pk=pk) #type:ignore

    if request.method == "POST":
        form = AppointmentEditForm(request.POST, clinic=clinic)

        if form.is_valid():
            try:
                AppointmentService.update_appointment(
                    appointment=appointment,
                    doctor=form.cleaned_data["doctor"],
                    appointment_type=form.cleaned_data["type"],
                    scheduled_at=form.cleaned_data.get("scheduled_at"),
                )
            except (ValueError, ValidationError) as e:
                form.add_error(None, str(e))
            else:
                messages.success(request, _("Appointment updated"))
                return redirect("patients:detail", pk=appointment.patient.pk)

    else:
        initial = {"doctor": appointment.doctor_id, "type": appointment.type.name if appointment.type else ""}
        if not appointment.is_walk_in:
            initial["scheduled_at"] = appointment.scheduled_at

        form = AppointmentEditForm(clinic=clinic, initial=initial)

    context = {"form": form, "appointment": appointment}
    return render(request, "appointments/edit.html", context)

