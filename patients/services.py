from .models import Patient

from billing.services import SubscriptionService

class PatientService:
    @staticmethod
    def get_for_clinic(clinic):
        return Patient.objects.for_clinic(clinic) #type:ignore

    @staticmethod
    def get_patient(clinic, patient_id):
        return Patient.objects.for_clinic(clinic).get(pk=patient_id) #type:ignore

    @staticmethod
    def create_patient(
        *,
        clinic,
        first_name,
        last_name,
        date_of_birth=None,
        approximate_age=None,
        phone="",
        address="",
        reason_for_visit="",
    ):
        if not SubscriptionService.can_add_patient(clinic):
            raise ValueError(
                "Your Trial plan is limited to 50 patients. Upgrade to continue adding patients."
            )

        return Patient.objects.create(
            clinic=clinic,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            approximate_age=approximate_age,
            phone=phone,
            address=address,
            reason_for_visit=reason_for_visit,
        )

    @staticmethod
    def update_patient(*, patient, first_name, last_name, date_of_birth=None,
                        approximate_age=None, phone="", address="", reason_for_visit=""):
        patient.first_name = first_name
        patient.last_name = last_name
        patient.date_of_birth = date_of_birth
        patient.approximate_age = approximate_age
        patient.phone = phone
        patient.address = address
        patient.reason_for_visit = reason_for_visit
        patient.save()

        return patient
    
