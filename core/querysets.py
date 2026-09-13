from django.db import models

class ClinicQuerySet(models.QuerySet):

    def for_clinic(self, clinic):
        return self.filter(clinic=clinic)

