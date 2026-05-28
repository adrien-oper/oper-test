"""Portal URL routes."""

from django.contrib.auth import views as auth_views
from django.urls import path

from portal.views import application, auth, dashboard, document, simulation

app_name = "portal"

urlpatterns = [
    path("", simulation.simulation_start, name="simulation_start"),
    path("dashboard/", dashboard.dashboard, name="dashboard"),
    path("signup/", auth.signup, name="signup"),
    path("signup/verify/", auth.verify_phone, name="verify_phone"),
    path("signup/office/", auth.choose_office, name="choose_office"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="portal/auth/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("simulation/<slug:slug>/", simulation.simulation_step, name="simulation_step"),
    path("simulation/income/add/", simulation.add_income_line, name="add_income_line"),
    path("simulation/income/<int:pk>/delete/", simulation.delete_income_line, name="delete_income_line"),
    path("simulation/expense/add/", simulation.add_expense_line, name="add_expense_line"),
    path("simulation/expense/<int:pk>/delete/", simulation.delete_expense_line, name="delete_expense_line"),
    path("simulation/<int:pk>/apply/", simulation.apply_to_simulation, name="apply_to_simulation"),
    path("apply/<int:pk>/recap/", application.apply_recap, name="apply_recap"),
    path("apply/<int:pk>/convert/", application.convert_simulation, name="convert_simulation"),
    path("application/<int:pk>/", application.application_detail, name="application_detail"),
    path("application/<int:pk>/form/", application.application_form, name="application_form"),
    path("application/<int:pk>/documents/upload/", document.upload_document, name="upload_document"),
    path("document/<int:pk>/", document.document_detail, name="document_detail"),
]
