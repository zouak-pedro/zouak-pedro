from django.utils import timezone
from django.core.exceptions import ValidationError

from billing.services import BillingService

from .models import Appointment, AppointmentType


class AppointmentTypeService:

    @staticmethod
    def suggest(query, limit=10):
        query = (query or "").strip()

        if not query:
            return AppointmentType.objects.none()

        return AppointmentType.objects.filter(name__icontains=query)[:limit]

    @staticmethod
    def get_or_create(name):
        name = (name or "").strip()

        if not name:
            return None

        existing = AppointmentType.objects.filter(name__iexact=name).first()
        if existing:
            return existing

        return AppointmentType.objects.create(name=name)


class AppointmentService:

    @staticmethod
    def get_for_day(clinic, day):
        return (
            Appointment.objects
            .for_clinic(clinic) #type:ignore
            .filter(scheduled_at__date=day)
            .select_related("patient", "doctor__user", "type")
        )

    @staticmethod
    def get_for_patient(clinic, patient, search=None, start_date=None, end_date=None):
        qs = (
            Appointment.objects
            .for_clinic(clinic) #type:ignore
            .filter(patient=patient)
            .select_related("doctor__user", "type")
        )

        if start_date:
            qs = qs.filter(scheduled_at__date__gte=start_date)

        if end_date:
            qs = qs.filter(scheduled_at__date__lte=end_date)

        if search:
            qs = qs.filter(type__name__icontains=search)

        return qs

    @staticmethod
    def create_appointment(*, clinic, patient, doctor, appointment_type, scheduled_at, created_by):
        if patient.clinic_id != clinic.id:
            raise ValueError("Patient does not belong to this clinic.")

        if doctor.clinic_id != clinic.id:
            raise ValueError("Doctor does not belong to this clinic.")

        if scheduled_at < timezone.now():
            raise ValidationError("You can't book an appointment in the past.")

        return Appointment.objects.create(
            clinic=clinic,
            patient=patient,
            doctor=doctor,
            type=appointment_type,
            scheduled_at=scheduled_at,
            status=Appointment.Status.SCHEDULED,
            is_walk_in=False,
            created_by=created_by,
        )
    @staticmethod
    def create_walk_in(*, clinic, patient, doctor, appointment_type, created_by):
        if patient.clinic_id != clinic.id:
            raise ValueError("Patient does not belong to this clinic.")

        if doctor.clinic_id != clinic.id:
            raise ValueError("Doctor does not belong to this clinic.")

        appointment = Appointment.objects.create(
            clinic=clinic,
            patient=patient,
            doctor=doctor,
            type=appointment_type,
            scheduled_at=timezone.now(),
            status=Appointment.Status.WAITING,
            is_walk_in=True,
            created_by=created_by,
        )

        BillingService.record_visit(appointment)

        return appointment

    EDITABLE_STATUSES = (
        Appointment.Status.SCHEDULED, Appointment.Status.ARRIVED,
        Appointment.Status.WAITING, Appointment.Status.WITH_DOCTOR,
    )

    @staticmethod
    def update_appointment(*, appointment, doctor, appointment_type, scheduled_at):
        if appointment.status not in AppointmentService.EDITABLE_STATUSES:
            raise ValueError("This appointment has already been completed, cancelled, or marked no-show and can no longer be edited.")

        if doctor.clinic_id != appointment.clinic_id:
            raise ValueError("Doctor does not belong to this clinic.")

        if not appointment.is_walk_in:
            if scheduled_at is None:
                raise ValueError("A date and time is required for a scheduled appointment.")
            if scheduled_at < timezone.now():
                raise ValidationError("You can't reschedule an appointment into the past.")
        appointment.doctor = doctor
        appointment.type = appointment_type
        if not appointment.is_walk_in:
            appointment.scheduled_at = scheduled_at
        appointment.save()

        return appointment    



    @staticmethod
    def update_status(*, appointment, new_status):
        valid_statuses = dict(Appointment.Status.choices)

        if new_status not in valid_statuses:
            raise ValueError("Invalid status.")

        appointment.status = new_status
        appointment.save(update_fields=["status", "updated_at"])

        BillingService.record_visit(appointment)

        return appointment