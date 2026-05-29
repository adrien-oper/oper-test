"""Apply flow: recap a simulation, convert it, fill the application, submit.

Conversion is a single guarded, atomic transition on the domain model. The
multi-step application form is a single ModelForm rendered as one page (the
brief blesses a single multi-step form); submission runs the FSM ``submit``
transition, which guards on the applicant details being present.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django_fsm import TransitionNotAllowed

from portal.forms import ApplicationDetailsForm
from portal.models import Application, Simulation, SimulationState
from portal.views._shared import get_owned_or_404


@login_required
def apply_recap(request: HttpRequest, pk: int) -> HttpResponse:
    """Show a recap of the simulation before converting it to an application."""
    simulation = get_owned_or_404(request, Simulation, pk)
    if simulation.state == SimulationState.CONVERTED:
        return redirect("portal:application_detail", pk=simulation.application.pk)
    if simulation.state != SimulationState.COMPLETED:
        messages.error(request, "Finish your simulation before applying.")
        return redirect("portal:dashboard")
    return render(
        request,
        "portal/application/recap.html",
        {"simulation": simulation, "report": simulation.feasibility()},
    )


@login_required
@require_POST
def convert_simulation(request: HttpRequest, pk: int) -> HttpResponse:
    """Convert a simulation into an application (guarded, atomic) and open the form.

    POST-only: conversion is state-changing, so it must not be reachable via a
    CSRF-free GET. It is driven by the CSRF-protected recap form.
    """
    simulation = get_owned_or_404(request, Simulation, pk)
    if simulation.state == SimulationState.CONVERTED:
        return redirect("portal:application_form", pk=simulation.application.pk)
    try:
        application = Application.create_from_simulation(simulation)
    except ValidationError:
        messages.error(request, "This simulation is not ready to convert. Complete it first.")
        return redirect("portal:apply_recap", pk=simulation.pk)
    messages.success(request, "Your application has been created. Complete the details below.")
    return redirect("portal:application_form", pk=application.pk)


@login_required
def application_form(request: HttpRequest, pk: int) -> HttpResponse:
    """The multi-step application form (personal/employment details)."""
    application = get_owned_or_404(request, Application, pk)
    if request.method == "POST":
        form = ApplicationDetailsForm(request.POST, instance=application)
        if form.is_valid():
            form.save()
            return _try_submit(request, form.instance)
    else:
        form = ApplicationDetailsForm(instance=application)
    return render(
        request,
        "portal/application/form.html",
        {"form": form, "application": application},
    )


def _try_submit(request: HttpRequest, application: Application) -> HttpResponse:
    """Run the guarded submit-then-review step, surfacing guard failures to the user."""
    try:
        application.submit_for_review()
    except TransitionNotAllowed:
        messages.error(request, "Please complete first name, last name and national number before submitting.")
        return redirect("portal:application_form", pk=application.pk)
    messages.success(request, "Your loan request has been submitted and is under review.")
    return redirect("portal:application_detail", pk=application.pk)


@login_required
def application_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Show an application's status and its uploaded documents."""
    application = get_owned_or_404(request, Application.objects.for_detail(), pk)
    return render(
        request,
        "portal/application/detail.html",
        {"application": application, "documents": application.documents.all()},
    )
