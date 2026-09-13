from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractUser
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField


# Create your models here.
class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email :
            raise ValueError(_("Email is required"))

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have 'is_superuser=True'.")

        return self.create_user(email=email, password=password, **extra_fields)

    def create_clinic_admin(self, *, email, password, clinic, first_name="", last_name=""):
        return self.create_user(email=email,
                                password=password,
                                clinic=clinic,
                                role=User.Role.DOCTOR,
                                is_clinic_admin=True,
                                first_name=first_name,
                                last_name=last_name)

    def create_doctor(self, *, email, password, clinic, first_name="", last_name=""):
            """Non-admin doctor — distinct from create_clinic_admin (is_clinic_admin=False)."""
            return self.create_user(email=email,
                                    password=password,
                                    clinic=clinic,
                                    role=User.Role.DOCTOR,
                                    is_clinic_admin=False,
                                    first_name=first_name,
                                    last_name=last_name)

    
    def create_secretary(self, *, email, password, clinic, first_name="", last_name=""):
        return self.create_user(email=email,
                                        password=password,
                                        clinic=clinic,
                                        role=User.Role.SECRETARY,
                                        is_clinic_admin=False,
                                        first_name=first_name,
                                        last_name=last_name)

    
class User(AbstractUser):
    class Role(models.TextChoices):
        DOCTOR = "doctor", _("Doctor")
        SECRETARY = "secretary", _("Secretary")

    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        FRENCH = "fr", "Français"

    role = models.CharField(max_length=20, choices=Role.choices)

    username = None #type:ignore

    email = models.EmailField(unique=True)

    phone = PhoneNumberField(blank=True)

    clinic = models.ForeignKey("clinics.Clinic", on_delete=models.PROTECT, related_name="users",null=True, blank=True)

    is_clinic_admin = models.BooleanField(default=False)

    language = models.CharField(max_length=10, choices=Language.choices, default=Language.ENGLISH)

    objects = UserManager()  #type:ignore

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.get_full_name() or self.email