from django.urls import path
from . import views

app_name = "appointments"

urlpatterns = [
    path("", views.day_view, name="day"),    
    path("add/", views.add_appointment, name="add"),    
    path("walk-in/", views.add_walk_in, name="walk_in"),    
    path("<int:pk>/edit/", views.edit_appointment, name="edit"),
    path("<int:pk>/status/", views.update_status, name="update_status"),    
    path("types/suggest/", views.appointment_type_suggest, name="type_suggest"),
    path("<str:date>/", views.day_view, name="day_for_date"),    
]
