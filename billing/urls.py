from django.urls import path
from . import views


app_name = "billing"

urlpatterns = [
    path("", views.subscription_status, name="status"),
    path("change-plan/", views.change_plan, name="change_plan"),
    path("select-plan/", views.select_plan, name="select_plan"),
    path("request-plan-change/", views.request_plan_change, name="request_plan_change"),
    path("invoices/<int:pk>/pay/", views.pay_invoice, name="pay_invoice"),
    path("payment-success/", views.payment_success, name="payment_success"),
    path("payment-failure/", views.payment_failure, name="payment_failure"),
    path("webhook/", views.chargily_webhook, name="webhook"),
]