from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required 
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.translation import gettext as _

from .profiles import DoctorProfile, SecretaryProfile

from .forms import ClinicRegistrationForm, DoctorCreateForm, SecretaryCreateForm, ClinicSettingsForm
from .services import ClinicService, SpecialtyService, StaffService

# Create your views here.

def register_clinic(request):
    if request.method == "POST":
        form = ClinicRegistrationForm(request.POST)

        if form.is_valid():
            try:
                clinic, doctor = ClinicService.create_clinic(
                    clinic_name=form.cleaned_data["clinic_name"],
                    clinic_phone=form.cleaned_data["clinic_phone"],
                    clinic_address=form.cleaned_data["clinic_address"],
                    doctor_email=form.cleaned_data["email"],
                    password=form.cleaned_data["password"],
                    first_name=form.cleaned_data["first_name"],
                    last_name=form.cleaned_data["last_name"],
                    specialty=form.cleaned_data["specialty"],
                )
            except IntegrityError:
                form.add_error("email", _("An account with this email already exist."))

            else:
                login(request, doctor.user)

                messages.success(request, _("Your clinic has been created successfully"))

                return redirect("core:dashboard")

    else:
        form = ClinicRegistrationForm()

    context = {"form": form}
    return render(request, "clinics/register.html", context)


def specialty_suggest(request):
    """
    Deliberately no @login_required — this powers autocomplete on the
    public clinic registration page, where nobody is authenticated yet.
    """
    query = request.GET.get("q", "")
    specialties = SpecialtyService.suggest(query)

    return JsonResponse({"results": [s.name for s in specialties]})


def _require_clinic_admin(request):
    clinic = request.user.clinic

    if clinic is None or not request.user.is_clinic_admin:
        raise PermissionDenied(_("Only a clinic administrator can manage staff."))

    return clinic

@login_required
def doctor_list(request):
    clinic = _require_clinic_admin(request)

    doctors = StaffService.get_doctors(clinic)

    context = {"doctors": doctors}
    return render(request, "clinics/doctor_list.html", context)


@login_required
def add_doctor(request):
    clinic = _require_clinic_admin(request)

    if request.method == "POST":
        form = DoctorCreateForm(request.POST)

        if form.is_valid():
            try:
                StaffService.create_doctor(
                    clinic=clinic,
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password"],
                    first_name=form.cleaned_data["first_name"],
                    last_name=form.cleaned_data["last_name"],
                    specialty=form.cleaned_data["specialty"],
                )
            except IntegrityError:
                form.add_error("email", _("An account with this email already exists."))
            except ValueError as e:
                form.add_error(None, str(e))
            else:
                messages.success(request, _("Doctor added successfully"))
                return redirect("clinics:doctor_list")

    else:
        form = DoctorCreateForm()

    context = {"form": form}
    return render(request, "clinics/doctor_add.html", context)


@login_required
def secretary_list(request):
    clinic = _require_clinic_admin(request)

    secretaries = StaffService.get_secretaries(clinic)

    context = {"secretaries": secretaries}
    return render(request, "clinics/secretary_list.html", context)


@login_required
def add_secretary(request):
    clinic = _require_clinic_admin(request)
    creating_doctor = request.user.doctor_profile

    if request.method == "POST":
        form = SecretaryCreateForm(request.POST)

        if form.is_valid():
            try:
                StaffService.create_secretary(
                    clinic=clinic,
                    created_by=creating_doctor,
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password"],
                    first_name=form.cleaned_data["first_name"],
                    last_name=form.cleaned_data["last_name"],
                )
            except IntegrityError:
                form.add_error("email", _("An account with this email already exists."))
            except ValueError as e:
                form.add_error(None, str(e))
            else:
                messages.success(request, _("Secretary added successfully"))
                return redirect("clinics:secretary_list")

    else:
        form = SecretaryCreateForm()

    context = {"form": form}
    return render(request, "clinics/secretary_add.html", context)



@login_required
def clinic_settings(request):
    clinic = _require_clinic_admin(request)

    if request.method == "POST":
        form = ClinicSettingsForm(request.POST, instance=clinic)

        if form.is_valid():
            form.save()
            messages.success(request, _("Clinic settings updated"))
            return redirect("clinics:settings")

    else:
        form = ClinicSettingsForm(instance=clinic)

    context = {"form": form}
    return render(request, "clinics/settings.html", context)  

@login_required
def doctor_detail(request, pk):
    clinic = _require_clinic_admin(request)

    doctor = get_object_or_404(DoctorProfile.objects.filter(clinic=clinic), pk=pk)

    context = {"doctor": doctor}
    return render(request, "clinics/doctor_detail.html", context)


@login_required
def secretary_detail(request, pk):
    clinic = _require_clinic_admin(request)

    secretary = get_object_or_404(SecretaryProfile.objects.filter(clinic=clinic), pk=pk)

    context = {"secretary": secretary}
    return render(request, "clinics/secretary_detail.html", context)


@login_required
@require_POST
def toggle_doctor_active(request, pk):
    clinic = _require_clinic_admin(request)

    doctor = get_object_or_404(DoctorProfile.objects.filter(clinic=clinic), pk=pk)

    try:
        StaffService.set_active(profile=doctor, is_active=not doctor.user.is_active)
    except ValueError as e:
        messages.error(request, str(e))
    else:
        if doctor.user.is_active:
            messages.success(request, _("Doctor activated"))
        else:
            messages.success(request, _("Doctor deactivated"))
    
    return redirect("clinics:doctor_detail", pk=pk)

@login_required
@require_POST
def toggle_secretary_active(request, pk):
    clinic = _require_clinic_admin(request)

    secretary = get_object_or_404(SecretaryProfile.objects.filter(clinic=clinic), pk=pk)

    try:
        StaffService.set_active(profile=secretary, is_active=not secretary.user.is_active)
    except ValueError as e:
        messages.error(request, str(e))
    else:
        if secretary.user.is_active:
            messages.success(request, _("Secretary activated"))
        else:
            messages.success(request, _("Secretary deactivated"))

    return redirect("clinics:secretary_detail", pk=pk)