from django import forms

from .models import Specialty, Clinic
from accounts.models import User

from django.contrib.auth.password_validation import validate_password

from .services import SpecialtyService

from django.utils.translation import gettext_lazy as _



class ClinicRegistrationForm(forms.Form):
    #-------------------
    # Clinic information
    #-------------------
    clinic_name = forms.CharField(max_length=200, label=_("Clinic name"),
                                  widget=forms.TelInput(
                                      attrs={
                                          "class": "form-control",
                                          "placeholder": _("Enter clinic name"),
                                      }
                                  )
                                )

    clinic_phone = forms.CharField(max_length=50, required=False, label=_("Phone number"),
                                   widget=forms.TelInput(
                                       attrs={
                                           "class": "form-control",
                                           "placeholder": _("Enter clinic phone number")
                                       }
                                   )
                                )
    clinic_address = forms.CharField(required=False, label=_("Address"), 
                                     widget=forms.Textarea(
                                         attrs={
                                             "class": "form-control",
                                             "rows": 3,
                                             "placeholder": _("Enter clinic address")
                                         }
                                     )
                                    )
    #-------------------
    # Doctor account
    #-------------------
    first_name = forms.CharField(max_length=150, label=_("First name"),
                                 widget=forms.TelInput(
                                     attrs={
                                        "class": "form-control",
                                        "placeholder": _("First name"),
                                     }
                                 )
                                )

    last_name = forms.CharField(max_length=150, label=_("Last name"),
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Last name"),
            }
        )
    )

    email = forms.EmailField(label=_("Email"),
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "doctor@example.com",
            }
        )
    )

    password = forms.CharField(label=_("Password"),
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Create a password"),
            }
        )
    )

    password_confirm = forms.CharField(label=_("Confirm password"),
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Confirm your password"),
            }
        )
    )   

    specialty = forms.CharField(
        max_length=150,
        label=_("Specialty"),        
        widget=forms.TextInput(
            attrs={
                "class": "form-control specialty-input",
                "placeholder": _("Start typing e.g. Cardiology"),
                "list": "specialty-suggestions",
                "autocomplete": "off",
            }
        )
    )

    #-------------------
    # Validation
    #-------------------

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()

        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(_("An account with this email already exists."))

        return email

    def clean_specialty(self):
        name = self.cleaned_data["specialty"].strip()

        if not name:
            raise forms.ValidationError(_("Specialty is required."))

        return SpecialtyService.get_or_create(name)

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("password") #type:ignore
        password_confirm = cleaned_data.get("password_confirm") #type:ignore

        if (password and password_confirm) and (password != password_confirm): 
            self.add_error(
                "password_confirm",
                _("Passwords do not match.")
            )

        if password:
            try:
                validate_password(password=password)
            except forms.ValidationError as error:
                self.add_error("password", error)


        return cleaned_data
        
        

class DoctorCreateForm(forms.Form):
    first_name = forms.CharField(max_length=150, label=_("First name"),
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("First name")}))

    last_name = forms.CharField(max_length=150, label=_("Last name"),
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("Last name")}))

    email = forms.EmailField(label=_("Email"),
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "doctor@example.com"}))

    password = forms.CharField(label=_("Password"),
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": _("Create a password")}))

    password_confirm = forms.CharField(label=_("Confirm password"),
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": _("Confirm password")}))

    specialty = forms.CharField(
        max_length=150, label=_("Specialty"),
        widget=forms.TextInput(attrs={
            "class": "form-control specialty-input",
            "placeholder": _("Start typing e.g. Cardiology"),
            "list": "specialty-suggestions",
            "autocomplete": "off",
        })
    )

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()

        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(_("An account with this email already exists."))

        return email

    def clean_specialty(self):
        name = self.cleaned_data["specialty"].strip()

        if not name:
            raise forms.ValidationError(_("Specialty is required."))

        return SpecialtyService.get_or_create(name)

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("password") #type:ignore
        password_confirm = cleaned_data.get("password_confirm") #type:ignore

        if password and password_confirm and password != password_confirm:
            self.add_error("password_confirm", _("Passwords do not match."))

        if password:
            try:
                validate_password(password=password)
            except forms.ValidationError as error:
                self.add_error("password", error)

        return cleaned_data


class SecretaryCreateForm(forms.Form):
    first_name = forms.CharField(max_length=150, label=_("First name"),
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder":_( "First name")}))

    last_name = forms.CharField(max_length=150, label=_("Last name"),
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("Last name")}))

    email = forms.EmailField(label=_("Email"),
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "secretary@example.com"}))

    password = forms.CharField(label=_("Password"),
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": _("Create a password")}))

    password_confirm = forms.CharField(label=_("Confirm password"),
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": _("Confirm password")}))

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()

        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(_("An account with this email already exists."))

        return email

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("password") #type:ignore
        password_confirm = cleaned_data.get("password_confirm") #type:ignore

        if password and password_confirm and password != password_confirm:
            self.add_error("password_confirm", _("Passwords do not match."))

        if password:
            try:
                validate_password(password=password)
            except forms.ValidationError as error:
                self.add_error("password", error)

        return cleaned_data


class ClinicSettingsForm(forms.ModelForm):
    class Meta:
        model = Clinic
        fields = [("name"), "phone", "address", "document_header", "document_footer"]
        widgets = {
            _("name"): forms.TextInput(attrs={"class": "form-control"}),
            _("phone"): forms.TextInput(attrs={"class": "form-control"}),
           _("address"): forms.Textarea(attrs={"class": "form-control", "rows": 3}),
           _("document_header"): forms.Textarea(attrs={
                "class": "form-control", "rows": 2,
                "placeholder": _("Optional text shown at the top of every printed document")
            }),
            _("document_footer"): forms.Textarea(attrs={
                "class": "form-control", "rows": 2,
                "placeholder": _("Optional text shown at the bottom of every printed document")
            }),
        }