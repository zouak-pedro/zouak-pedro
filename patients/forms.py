from django import forms
from phonenumber_field.formfields import PhoneNumberField
from django.utils.translation import gettext_lazy as _

class PatientForm(forms.Form):
    first_name = forms.CharField( #type:ignore
        max_length=150,
        label=_("First name"),
        widget=forms.TextInput(
                         attrs={
                               "class": "form-control",
                                "placeholder": _("First name"),
                                }
                            )
    )
    
    last_name = forms.CharField(
        max_length=150,
        label=_("Last name"),
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Last name"),
            }
        )
    )

    date_of_birth = forms.DateField(
        required=False,
        label=_("Date of birth"),
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": _("date"),
            }
        )
    )

    approximate_age = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=130,
        label=_("Approximate age (if DOB unknown)"),
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": _("e.g. 45"),
            }
        )
    )

    phone = PhoneNumberField(  #type:ignore
        required=False,
        label=_("Phone"),
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": _("+213 555 12 34 56"),
            }
        )
    )

    address = forms.CharField(
        required=False,
        label=_("Address"),
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 2,
                "placeholder": _("Enter patient address"),
            }
        )
    )

    reason_for_visit = forms.CharField(
        required=False,
        max_length=255,
        label=_("Reason for visit"),
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": _("e.g. follow-up, chest pain, prescription renewal"),
            }
        )
    )