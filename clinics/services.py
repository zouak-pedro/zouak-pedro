from django.core.exceptions import ValidationError
from django.db import transaction
from django.contrib.sessions.models import Session
from django.utils import timezone

from billing.services import SubscriptionService
from accounts.models import User

from .models import Clinic, Specialty
from .profiles import DoctorProfile, SecretaryProfile


class SpecialtyService:

    @staticmethod
    def suggest(query, limit=10):
        query = (query or "").strip() 

        if not query:
            return Specialty.objects.none()

        return Specialty.objects.filter(is_active=True, name__icontains=query)[:limit]

    @staticmethod
    def get_or_create(name):
        """
        Case-insensitive lookup/create, same pattern as records.MedicationService.
        Matches against ALL specialties regardless of is_active, so typing an
        existing-but-deactivated specialty's name reuses it rather than creating
        a duplicate — is_active status itself is left untouched either way.
        """
        name = (name or "").strip()

        if not name:
            return None

        existing = Specialty.objects.filter(name__iexact=name).first()
        if existing:
            return existing

        return Specialty.objects.create(name=name, is_active=True)


class StaffService:

    @staticmethod
    @transaction.atomic
    def create_doctor(*, clinic, email, password, first_name, last_name, specialty):
        if not SubscriptionService.can_add_doctor(clinic):
            raise ValueError(
                "Your current plan allows only 1 doctor. Upgrade to Pay-per-visit for unlimited staff."
            )

        user = User.objects.create_doctor( #type:ignore
            email=email, password=password, clinic=clinic,
            first_name=first_name, last_name=last_name,
        )

        return DoctorProfile.objects.create(user=user, clinic=clinic, specialty=specialty)

    @staticmethod
    @transaction.atomic
    def create_secretary(*, clinic, created_by, email, password, first_name, last_name):
        if created_by.clinic_id != clinic.id:
            raise ValueError("The creating doctor does not belong to this clinic.")

        if not SubscriptionService.can_add_secretary(clinic):
            raise ValueError(
                "Your current plan allows only 1 secretary. Upgrade to Pay-per-visit for unlimited staff."
            )

        user = User.objects.create_secretary( #type:ignore
            email=email, password=password, clinic=clinic,
            first_name=first_name, last_name=last_name,
        )

        return SecretaryProfile.objects.create(user=user, clinic=clinic, created_by=created_by)

    @staticmethod
    def get_doctors(clinic):
        return DoctorProfile.objects.filter(clinic=clinic).select_related("user", "specialty")

    @staticmethod
    def get_secretaries(clinic):
        return SecretaryProfile.objects.filter(clinic=clinic).select_related("user", "created_by__user")

    @staticmethod
    def get_doctor(clinic, doctor_id):
        return DoctorProfile.objects.select_related("user", "specialty").get(clinic=clinic, pk=doctor_id)

    @staticmethod
    def get_secretary(clinic, secretary_id):
        return SecretaryProfile.objects.select_related("user", "created_by__user").get(clinic=clinic, pk=secretary_id)

    @staticmethod
    def set_active(*, profile, is_active):
        """
        Works for both DoctorProfile and SecretaryProfile — both expose
        `.user`, so this stays generic rather than duplicated per role.
        Guards against a clinic-admin deactivating their own account,
        which would otherwise be an unrecoverable lockout (no other admin
        exists to reactivate them).
        """
        if profile.user.is_clinic_admin and not is_active:
            raise ValueError("You cannot deactivate the clinic administrator account.")

        profile.user.is_active = is_active
        profile.user.save(update_fields=["is_active"])

        if not is_active:
            StaffService._kill_active_sessions_for(profile.user)

        return profile

    @staticmethod
    def _kill_active_sessions_for(user):
        """
        Deactivation should end access immediately, not just block future
        logins — without this, a user already logged in when deactivated
        keeps working access until their session naturally expires.
        O(n) over all active sessions; acceptable at current scale.
        """
        for session in Session.objects.filter(expire_date__gte=timezone.now()):
            data = session.get_decoded()
            if str(data.get("_auth_user_id")) == str(user.pk):
                session.delete()


class ClinicService:
    @staticmethod
    @transaction.atomic
    def create_clinic(
                        *,
                        clinic_name,
                        doctor_email,
                        password,
                        first_name,
                        last_name,
                        specialty,                    
                        clinic_phone="",
                        clinic_email="",
                        clinic_address="",
                        
    ):
        
        # 1. Create the clinic
        clinic = Clinic.objects.create(name=clinic_name,
                                        phone=clinic_phone,                                  
                                        address=clinic_address)


        # 2. Create the doctor User
        user = User.objects.create_clinic_admin( #type:ignore
            email=doctor_email,
            password=password,
            clinic=clinic,
            first_name=first_name,
            last_name=last_name
        )

        # 3. Create the doctor's professional profile
        doctor = DoctorProfile.objects.create(
            user=user,
            clinic=clinic,
            specialty=specialty
        )

        SubscriptionService.create_trial(clinic)

        return clinic, doctor

    @staticmethod
    def validate_doctor_profile(*, user, clinic, specialty):
        if user.clinic_id != clinic.id:
            raise ValueError("The doctor user does not belong to this clinic.")

        if user.role != User.Role.DOCTOR:
            raise ValueError("The user must have the doctor role.")

        if not user.is_clinic_admin:
            raise ValueError("The doctor must be a clinic administrator.")

        if specialty is None:
            raise ValueError("A specialty is required.")




