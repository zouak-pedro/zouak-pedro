from django import forms
from django.utils.translation import gettext_lazy as _

from .models import PlanChangeRequest


class PlanChangeRequestForm(forms.ModelForm):
    class Meta:
        model = PlanChangeRequest
        fields = ["requested_plan", "payment_method", "proof_file", "reference_note"]
        widgets = {
            _("requested_plan"): forms.Select(attrs={"class": "form-select"}),
            _("payment_method"): forms.Select(attrs={"class": "form-select"}),
            _("proof_file"): forms.ClearableFileInput(attrs={"class": "form-control"}),
            _("reference_note"): forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": _("e.g. transfer reference number (optional)")
            }),
        }