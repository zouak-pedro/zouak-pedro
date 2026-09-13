from django.urls import path
from . import views

app_name = "patients"

urlpatterns = [ 
    path("", views.patient_list, name="list"),
    path("add/", views.add_patient, name="add"),
    path("<int:pk>/", views.patient_detail, name="detail"),
    path("<int:pk>/edit/", views.edit_patient, name="edit"),

    path("<int:patient_id>/prescriptions/add/", views.add_prescription, name="add_prescription"),
    path("<int:patient_id>/prescriptions/<int:pk>/edit/", views.edit_prescription, name="edit_prescription"),

    path("<int:patient_id>/notes/add/", views.add_note, name="add_note"),
    path("<int:patient_id>/notes/<int:pk>/edit/", views.edit_note, name="edit_note"),

    path("<int:patient_id>/procedure-reports/add/", views.add_procedure_report, name="add_procedure_report"),
    path("<int:patient_id>/procedure-reports/<int:pk>/edit/", views.edit_procedure_report, name="edit_procedure_report"),

    path("<int:patient_id>/labwork-demands/add/", views.add_labwork_demand, name="add_labwork_demand"),
    path("<int:patient_id>/labwork-demands/<int:pk>/edit/", views.edit_labwork_demand, name="edit_labwork_demand"),

] 
