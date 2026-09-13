from django.test import TestCase
from django.urls import reverse

from .models import User
# Create your tests here.

class AuthenticationTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(     #type:ignore
            email="doctor@example.com",
            password="StrongPassword123!",
            first_name="John",
            last_name="Doe",
        )

    def test_login_page_is_accessible(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertEqual(response.status_code, 200)

    def test_user_can_login_with_email(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "email": "doctor@example.com",
                "password": "StrongPassword123!",
            }
        )
        self.assertRedirects(response, reverse("core:dashboard"))

        

        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_invalid_password_does_not_login(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "email": "doctor@example.com",
                "password": "WrongPassword123!",
            }
        )

        self.assertEqual(response.status_code, 200)

        self.assertFalse(response.wsgi_request.user.is_authenticated)



    def test_logout(self):
        self.client.login(
            email="doctor@example.com",
            password="StrongPassword123!",
        )

        response = self.client.post(reverse("accounts:logout"))

        self.assertRedirects(response, reverse("accounts:login"))

        response = self.client.get(reverse("core:dashboard"))

        self.assertRedirects(response, '/accounts/login/?next=/dashboard/')



class ProfileEditTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user( #type:ignore
            email="doctor@example.com",
            password="StrongPassword123!",
            first_name="John",
            last_name="Doe",
        )

    def test_edit_profile_requires_login(self):
        response = self.client.get(reverse("accounts:edit_profile"))
        self.assertEqual(response.status_code, 302)

    def test_can_update_profile_fields(self):
        self.client.login(email="doctor@example.com", password="StrongPassword123!")

        response = self.client.post(reverse("accounts:edit_profile"), {
            "update_profile": "1",
            "first_name": "Jonathan",
            "last_name": "Doe",
            "email": "doctor@example.com",
            "phone": "+213555123456",
            "language": "en",
        })

        self.assertRedirects(response, reverse("accounts:edit_profile"))

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Jonathan")
        self.assertEqual(str(self.user.phone), "+213555123456")

    def test_cannot_change_email_to_one_already_in_use(self):
        User.objects.create_user(email="taken@example.com", password="pw") #type:ignore

        self.client.login(email="doctor@example.com", password="StrongPassword123!")

        response = self.client.post(reverse("accounts:edit_profile"), {
            "update_profile": "1",
            "first_name": "John",
            "last_name": "Doe",
            "email": "taken@example.com",
            "phone": "",
            "language": "en",
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["profile_form"].is_valid())
    def test_can_change_password(self):
        self.client.login(email="doctor@example.com", password="StrongPassword123!")

        response = self.client.post(reverse("accounts:edit_profile"), {
            "change_password": "1",
            "old_password": "StrongPassword123!",
            "new_password1": "EvenStrongerPassword456!",
            "new_password2": "EvenStrongerPassword456!",
        })

        self.assertRedirects(response, reverse("accounts:edit_profile"))

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("EvenStrongerPassword456!"))

    def test_wrong_old_password_rejected(self):
        self.client.login(email="doctor@example.com", password="StrongPassword123!")

        response = self.client.post(reverse("accounts:edit_profile"), {
            "change_password": "1",
            "old_password": "WrongPassword",
            "new_password1": "EvenStrongerPassword456!",
            "new_password2": "EvenStrongerPassword456!",
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["password_form"].is_valid())

    def test_session_survives_password_change(self):
        self.client.login(email="doctor@example.com", password="StrongPassword123!")

        self.client.post(reverse("accounts:edit_profile"), {
            "change_password": "1",
            "old_password": "StrongPassword123!",
            "new_password1": "EvenStrongerPassword456!",
            "new_password2": "EvenStrongerPassword456!",
        })

        # If update_session_auth_hash was forgotten, this would now redirect to login
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_password_form_fields_have_bootstrap_styling(self):
        self.client.login(email="doctor@example.com", password="StrongPassword123!")

        response = self.client.get(reverse("accounts:edit_profile"))

        password_form = response.context["password_form"]
        self.assertIn("form-control", password_form.fields["old_password"].widget.attrs.get("class", ""))
        self.assertIn("form-control", password_form.fields["new_password1"].widget.attrs.get("class", ""))
        self.assertIn("form-control", password_form.fields["new_password2"].widget.attrs.get("class", ""))