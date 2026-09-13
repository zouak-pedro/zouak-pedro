from django.db import models

from .context import get_current_clinic
from .querysets import ClinicQuerySet

class ClinicManager(models.Manager):

    def get_queryset(self) -> models.QuerySet:
        qs = ClinicQuerySet(self.model, using=self._db)

        clinic = get_current_clinic()
        if clinic is not None:
            qs = qs.filter(clinic=clinic)

        return qs

    def for_clinic(self, clinic):
        # Explicit override - bypasses the context-var clinic,
        # useful for management commands, admin, or background jobs
        # where there's no request cycle setting the context var.
        return ClinicQuerySet(self.model, using=self._db).filter(clinic=clinic)

    def unscoped(self):
        """Escape hatch for legitimate cross-tenant access (superuser tooling, migrations)"""
        return ClinicQuerySet(self.model, using=self._db)

    

    