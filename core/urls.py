from django.urls import path
from .views import audit_log_view, dashboard, set_language


app_name = "core"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("audit-log/", audit_log_view, name="audit_log"),
    path("set-language/", set_language, name="set_language"),
]
