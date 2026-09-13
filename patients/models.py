from django.db import models
from core.models import ClinicOwnedModel
from phonenumber_field.modelfields import PhoneNumberField

from django.utils import timezone

# Create your models here.

class Patient(ClinicOwnedModel):
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)

    date_of_birth = models.DateField(null=True, blank=True)
    approximate_age = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Only used when exact date of birth isn't known/given"
    )

    phone = PhoneNumberField(unique=False, blank=True)
    address = models.TextField(blank=True)

    reason_for_visit = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        """
        Live-computed age. Prefers exact date_of_birth (always accurate,
        recalculated on every access), falls back to the staff-entered
        approximate_age when no DOB was given. Return None if neither is available.
        """
        if  self.date_of_birth:
            today = timezone.localdate()
            years = today.year - self.date_of_birth.year 
            had_birthday_this_year = (today.month, today.day) >= (
                self.date_of_birth.month, self.date_of_birth.day
            )
            if not had_birthday_this_year:
                years -= 1
                return years

        return self.approximate_age