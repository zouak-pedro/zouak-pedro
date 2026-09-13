from django.urls import path
from . import views

app_name = "records"

urlpatterns = [
    path("prescriptions/<int:pk>/print/", views.prescription_print, name="prescription_print"),

    path("medications/suggest/", views.medication_suggest, name="medication_suggest"),

    path("notes/<int:pk>/print/", views.note_print, name="note_print"),

    path("procedure-reports/<int:pk>/print/", views.procedure_report_print, name="procedure_report_print"),

    path("labwork-demands/<int:pk>/print/", views.labwork_demand_print, name="labwork_demand_print"),

    path("document-profile/", views.edit_document_profile, name="edit_document_profile"),

]
