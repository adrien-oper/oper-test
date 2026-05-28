"""The anonymous simulation wizard and its live feasibility report.

The wizard works without an account: the simulation id is held in the
session until the visitor signs up, at which point it is claimed. Each step
is a small form over the shared Simulation row; navigation and the sidebar
read from ``portal.wizard``.
"""

from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from portal import forms, wizard
from portal.models import ExpenseLine, IncomeLine, Simulation, SimulationState

_STEP_FORMS = {
    "purpose": forms.PurposeForm,
    "borrowers": forms.BorrowersForm,
    "project": forms.ProjectForm,
    "contribution": forms.ContributionForm,
    "personal": forms.PersonalForm,
}


def _current_simulation(request: HttpRequest) -> Simulation | None:
    """Return the in-progress simulation for this session, if any."""
    sim_id = request.session.get(wizard.SIMULATION_SESSION_KEY)
    if not sim_id:
        return None
    return Simulation.objects.filter(pk=sim_id).first()


def _get_or_start(request: HttpRequest) -> Simulation:
    """Return the session's simulation, creating a fresh draft if needed."""
    simulation = _current_simulation(request)
    if simulation is None or simulation.state == SimulationState.CONVERTED:
        simulation = Simulation.objects.create(
            user=request.user if request.user.is_authenticated else None,
        )
        request.session[wizard.SIMULATION_SESSION_KEY] = simulation.pk
    return simulation


def _sidebar(active_slug: str) -> list[dict[str, object]]:
    """Build the step sidebar entries with completion state."""
    active_index = wizard.step_index(active_slug)
    return [
        {
            "slug": step.slug,
            "label": step.label,
            "group": step.group,
            "done": index < active_index,
            "active": step.slug == active_slug,
        }
        for index, step in enumerate(wizard.SIMULATION_STEPS)
    ]


def simulation_start(request: HttpRequest) -> HttpResponse:
    """Landing page — begin a brand-new simulation."""
    request.session.pop(wizard.SIMULATION_SESSION_KEY, None)
    return redirect("portal:simulation_step", slug="purpose")


@require_http_methods(["GET", "POST"])
def simulation_step(request: HttpRequest, slug: str) -> HttpResponse:
    """Render or process one wizard step."""
    if slug == "report":
        return _report(request)
    if slug == "income":
        return _financial_step(request, slug, IncomeLine, "incomes")
    if slug == "expenses":
        return _financial_step(request, slug, ExpenseLine, "expenses")
    return _model_step(request, slug)


def _model_step(request: HttpRequest, slug: str) -> HttpResponse:
    simulation = _get_or_start(request)
    form_class = _STEP_FORMS[slug]
    if request.method == "POST":
        form = form_class(request.POST, instance=simulation)
        if form.is_valid():
            form.save()
            nxt = wizard.next_slug(slug)
            return redirect("portal:simulation_step", slug=nxt)
    else:
        form = form_class(instance=simulation)
    return render(
        request,
        "portal/simulation/step.html",
        {
            "form": form,
            "slug": slug,
            "sidebar": _sidebar(slug),
            "previous": wizard.previous_slug(slug),
            "simulation": simulation,
        },
    )


def _financial_step(request: HttpRequest, slug: str, model: type, relation: str) -> HttpResponse:
    """Income/expense add-row steps. POST advances; rows are added via HTMX."""
    simulation = _get_or_start(request)
    if request.method == "POST":
        return redirect("portal:simulation_step", slug=wizard.next_slug(slug))
    form = forms.IncomeLineForm() if model is IncomeLine else forms.ExpenseLineForm()
    return render(
        request,
        "portal/simulation/financial.html",
        {
            "slug": slug,
            "sidebar": _sidebar(slug),
            "previous": wizard.previous_slug(slug),
            "simulation": simulation,
            "lines": getattr(simulation, relation).all(),
            "line_form": form,
        },
    )


@require_http_methods(["POST"])
def add_income_line(request: HttpRequest) -> HttpResponse:
    """HTMX: append an income row and swap the rows partial back."""
    simulation = _get_or_start(request)
    form = forms.IncomeLineForm(request.POST)
    if form.is_valid():
        line = form.save(commit=False)
        line.simulation = simulation
        line.save()
    return render(
        request,
        "portal/simulation/_income_rows.html",
        {"lines": simulation.incomes.all(), "line_form": forms.IncomeLineForm()},
    )


@require_http_methods(["POST"])
def add_expense_line(request: HttpRequest) -> HttpResponse:
    """HTMX: append an expense row and swap the rows partial back."""
    simulation = _get_or_start(request)
    form = forms.ExpenseLineForm(request.POST)
    if form.is_valid():
        line = form.save(commit=False)
        line.simulation = simulation
        line.save()
    return render(
        request,
        "portal/simulation/_expense_rows.html",
        {"lines": simulation.expenses.all(), "line_form": forms.ExpenseLineForm()},
    )


@require_http_methods(["POST"])
def delete_income_line(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX: remove an income row and swap the rows partial back."""
    simulation = _get_or_start(request)
    simulation.incomes.filter(pk=pk).delete()
    return render(
        request,
        "portal/simulation/_income_rows.html",
        {"lines": simulation.incomes.all(), "line_form": forms.IncomeLineForm()},
    )


@require_http_methods(["POST"])
def delete_expense_line(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX: remove an expense row and swap the rows partial back."""
    simulation = _get_or_start(request)
    simulation.expenses.filter(pk=pk).delete()
    return render(
        request,
        "portal/simulation/_expense_rows.html",
        {"lines": simulation.expenses.all(), "line_form": forms.ExpenseLineForm()},
    )


def _decimal_param(request: HttpRequest, name: str) -> Decimal | None:
    raw = request.GET.get(name)
    if not raw:
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, TypeError):
        return None


def _int_param(request: HttpRequest, name: str) -> int | None:
    raw = request.GET.get(name)
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _report(request: HttpRequest) -> HttpResponse:
    """Render the feasibility report (full page or HTMX slider partial)."""
    simulation = _current_simulation(request)
    if simulation is None:
        return redirect("portal:simulation_start")

    if simulation.state == SimulationState.DRAFT and simulation.incomes.exists():
        simulation.complete()
        simulation.save()

    own_funds_override = _decimal_param(request, "own_funds")
    duration = _int_param(request, "duration")
    report = simulation.feasibility(own_funds_override=own_funds_override, duration_years=duration)

    context = {
        "simulation": simulation,
        "report": report,
        "sidebar": _sidebar("report"),
        "previous": wizard.previous_slug("report"),
        "min_funds": 0,
        "max_funds": int(report.total_project_cost),
    }
    if request.headers.get("HX-Request"):
        return render(request, "portal/simulation/_report_card.html", context)
    return render(request, "portal/simulation/report.html", context)


@login_required
def apply_to_simulation(request: HttpRequest, pk: int) -> HttpResponse:
    """Entry point for the apply flow — lands on the simulation recap."""
    get_object_or_404(Simulation, pk=pk, user=request.user)
    return redirect("portal:apply_recap", pk=pk)
