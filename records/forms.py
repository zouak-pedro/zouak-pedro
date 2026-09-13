from django import forms 
from django.forms import formset_factory
from django.utils.translation import gettext_lazy as _

from clinics.profiles import DoctorProfile
from patients.models import Patient

from .models import LabworkDemand, DoctorDocumentProfile

class PrescriptionForm(forms.Form):

    doctor = forms.ModelChoiceField(
        queryset=DoctorProfile.objects.none(),
        label=_("Doctor"),
        widget=forms.Select(attrs={"class": "form-select"})
    )

    patient_name_override = forms.CharField(
        max_length=300, required=False,
        label=_("Patient name on this prescription (optional)"),
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": _("Leave blank to use the patient's name on file"),
        })
    )

    notes = forms.CharField(
        required=False,
        label=_("Notes"),
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2})
    )

    def __init__(self, *args, clinic=None, **kwargs):
        super().__init__(*args, **kwargs)

        if clinic is not None:
            self.fields["doctor"].queryset = DoctorProfile.objects.filter(clinic=clinic, user__is_active=True)  #type:ignore


class PrescriptionItemForm(forms.Form):

    medication_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            "class": "form-control medication-name-input",
            "placeholder": _("Medication name"),
            "list": "medication-suggestions",
            "autocomplete": "off",
        })
    )
    dosage = forms.CharField(
            max_length=100, required=False,
            widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("Dosage")})
        )
    frequency = forms.CharField(
            max_length=100, required=False,
            widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("Frequency")})
        )
    duration = forms.CharField(
            max_length=100, required=False,
            widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("Duration")})
        )
    instructions = forms.CharField(
            max_length=255, required=False,
            widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("Instructions")})
        )

PrescriptionItemFormSet = formset_factory(PrescriptionItemForm, extra=3, can_delete=True)


class DoctorNoteForm(forms.Form):

    doctor = forms.ModelChoiceField(
        queryset=DoctorProfile.objects.none(),
        label=_("Doctor"),
        widget=forms.Select(attrs={"class": "form-select"})
    )

    content = forms.CharField(
        label=_("Note"),
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 6})
    )

    def __init__(self, *args, clinic=None, **kwargs):
        super().__init__(*args, **kwargs)

        if clinic is not None:
            self.fields["doctor"].queryset = DoctorProfile.objects.filter(clinic=clinic, user__is_active=True) #type:ignore



class ProcedureReportForm(forms.Form):
   
    doctor = forms.ModelChoiceField(queryset=DoctorProfile.objects.none(), label=_("Doctor"), widget=forms.Select(attrs={"class": "form-select"}))
    notes = forms.CharField(required=False, label=_("General notes"), widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}))

    def __init__(self, *args, clinic=None, **kwargs):
        super().__init__(*args, **kwargs)
        if clinic is not None:
            self.fields["doctor"].queryset = DoctorProfile.objects.filter(clinic=clinic, user__is_active=True) #type:ignore


class ProcedureItemForm(forms.Form):
    procedure_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("Procedure name")})
    )
    findings = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": _("Findings / notes")})
    )


ProcedureItemFormSet = formset_factory(ProcedureItemForm, extra=2, can_delete=True)


class LabworkDemandForm(forms.Form):
 
    doctor = forms.ModelChoiceField(queryset=DoctorProfile.objects.none(), label=_("Doctor"), widget=forms.Select(attrs={"class": "form-select"}))

    def __init__(self, *args, clinic=None, **kwargs):
        super().__init__(*args, **kwargs)
        if clinic is not None:
            self.fields["doctor"].queryset = DoctorProfile.objects.filter(clinic=clinic, user__is_active=True) #type:ignore


class LabworkItemForm(forms.Form):
    test_name = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("Test name")})
    )
    urgency = forms.ChoiceField(
        choices=LabworkDemand.Urgency.choices, 
        widget=forms.Select(attrs={"class": "form-select"})
    )
    clinical_indication = forms.CharField(
        max_length=255, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("Clinical indication / reason")})
    )


LabworkItemFormSet = formset_factory(LabworkItemForm, extra=2, can_delete=True)


class DoctorDocumentProfileForm(forms.ModelForm):
    class Meta:
        model = DoctorDocumentProfile
        fields = ["professional_title", "registration_number", "signature", "stamp"]
        widgets = {
            _("professional_title"): forms.TextInput(attrs={
                "class": "form-control", "placeholder": _("e.g. General Practitioner")
            }),
            _("registration_number"): forms.TextInput(attrs={
                "class": "form-control", "placeholder": _("Medical registration number")
            }),
            _("signature"): forms.ClearableFileInput(attrs={"class": "form-control"}),
            _("stamp"): forms.ClearableFileInput(attrs={"class": "form-control"}),
        }