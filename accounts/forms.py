from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from phonenumber_field.formfields import PhoneNumberField
from django.utils.translation import gettext_lazy as _

from .models import User


class LoginForm(forms.Form):
    email = forms.EmailField(label="Email",
                             widget=forms.EmailInput(
                                 attrs={
                                     "class": "form-control",
                                     "placeholder": "Enter your email",
                                     "autocomplete": "email",
                                 }
                             ))

    password = forms.CharField(label="Password",
                               widget=forms.PasswordInput(
                                   attrs={
                                        "class": "form-control",
                                        "placeholder": "Enter your password",
                                        "autocomplete": "current-password",
                                   }
                               ))



class ProfileForm(forms.ModelForm):
    phone = PhoneNumberField(
        required=False,
        label=_("Phone"),
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "+213 555 12 34 56"})
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "language"]
        labels = {
            "first_name": _("First name"),
            "last_name": _("Last name"),
            "email": _("Email"),
            "language": _("Language"),
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "language": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()

        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("An account with this email already exists."))

        return email


class StyledPasswordChangeForm(PasswordChangeForm):
    """
    Django's built-in PasswordChangeForm ships with no widget classes at
    all — this subclass just layers Bootstrap's form-control class onto
    each field so it matches the rest of the app. No validation logic
    changes; everything else behaves exactly like the parent form.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["old_password"].widget.attrs.update({
            "class": "form-control",
            "placeholder": _("Current password"),
            "autocomplete": "current-password",
        })
        self.fields["new_password1"].widget.attrs.update({
            "class": "form-control",
            "placeholder": _("New password"),
            "autocomplete": "new-password",
        })
        self.fields["new_password2"].widget.attrs.update({
            "class": "form-control",
            "placeholder": _("Confirm new password"),
            "autocomplete": "new-password",
        })