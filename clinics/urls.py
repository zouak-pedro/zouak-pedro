from django.urls import path
from . import views

app_name = "clinics"

urlpatterns = [
    path("register/", views.register_clinic, name="register"),
    path("specialties/suggest/", views.specialty_suggest, name="specialty_suggest"),

    path("doctors/", views.doctor_list, name="doctor_list"),
    path("doctors/add/", views.add_doctor, name="doctor_add"),

    path("doctors/<int:pk>/", views.doctor_detail, name="doctor_detail"),
    path("doctors/<int:pk>/toggle-active/", views.toggle_doctor_active, name="doctor_toggle_active"),
    
    
    path("secretaries/", views.secretary_list, name="secretary_list"),
    path("secretaries/add/", views.add_secretary, name="secretary_add"),

    path("secretaries/<int:pk>/", views.secretary_detail, name="secretary_detail"),
    path("secretaries/<int:pk>/toggle-active/", views.toggle_secretary_active, name="secretary_toggle_active"),
    

    path("settings/", views.clinic_settings, name="settings"),
]
