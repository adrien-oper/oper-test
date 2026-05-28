"""Apply flow: recap a simulation, convert it, fill the application, submit.

Conversion is a single guarded, atomic transition on the domain model. The
multi-step application form is a single ModelForm rendered as one page (the
brief blesses a single multi-step form); submission runs the FSM ``submit``
transition, which guards on the applicant details being present.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django_fsm import TransitionNotAllowed

from portal.forms import ApplicationDetailsForm
from portal.models import Application, Simulation, SimulationState


@login_required
def apply_recap(request: HttpRequest, pk: int) -> HttpResponse:
    """Show a recap of the simulation before converting it to an application."""
    simulation = get_object_or_404(Simulation, pk=pk, user=request.user)
    if simulation.state == SimulationState.CONVERTED:
        return redirect("portal:application_detail", pk=simulation.application.pk)
    return render(
        request,
        "portal/application/recap.html",
        {"simulation": simulation, "report": simulation.feasibility()},
    )


@login_required
def convert_simulation(request: HttpRequest, pk: int) -> HttpResponse:
    """Convert a simulation into an application (guarded, atomic) and open the form."""
    simulation = get_object_or_404(Simulation, pk=pk, user=request.user)
    if simulation.state == SimulationState.CONVERTED:
        application = simulation.application
    else:
        application = Application.create_from_simulation(simulation)
        messages.success(request, "Your application has been created. Complete the details below.")
    return redirect("portal:application_form", pk=application.pk)


@login_required
def application_form(request: HttpRequest, pk: int) -> HttpResponse:
    """The multi-step application form (personal/employment details)."""
    application = get_object_or_404(Application, pk=pk, user=request.user)
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
    """Run the guarded submit transition, surfacing guard failures to the user."""
    try:
        application.submit()
    except TransitionNotAllowed:
        messages.error(request, "Please complete first name, last name and national number before submitting.")
        return redirect("portal:application_form", pk=application.pk)
    application.save()
    application.start_review()
    application.save()
    messages.success(request, "Your loan request has been submitted and is under review.")
    return redirect("portal:application_detail", pk=application.pk)


@login_required
def application_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Show an application's status and its uploaded documents."""
    application = get_object_or_404(Application, pk=pk, user=request.user)
    return render(
        request,
        "portal/application/detail.html",
        {"application": application, "documents": application.documents.all()},
    )
