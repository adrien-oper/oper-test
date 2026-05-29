"""Sign-up flow: account creation, phone verification (stub), help office.

On sign-up the anonymous simulation held in the session is claimed by the
new user, so the journey continues seamlessly into the dashboard. The
onboarding choices (phone verification, help office) are persisted on a
:class:`~portal.models.reference.BorrowerProfile` so they survive logout.
"""

from django.contrib.auth import login
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from portal import wizard
from portal.forms_auth import HelpOfficeForm, PhoneVerificationForm, SignupForm
from portal.models import BorrowerProfile, HelpOffice, Simulation


def _claim_session_simulation(request: HttpRequest) -> None:
    """Attach the session's anonymous simulation to the freshly-signed-up user."""
    sim_id = request.session.get(wizard.SIMULATION_SESSION_KEY)
    if sim_id:
        Simulation.objects.filter(pk=sim_id, user__isnull=True).update(user=request.user)


def signup(request: HttpRequest) -> HttpResponse:
    """Create an account (email + password + consent) and sign in."""
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            BorrowerProfile.objects.get_or_create(user=user)
            _claim_session_simulation(request)
            return redirect("portal:verify_phone")
    else:
        form = SignupForm()
    return render(request, "portal/auth/signup.html", {"form": form})


def verify_phone(request: HttpRequest) -> HttpResponse:
    """Phone-number verification — stubbed: any 6-digit code is accepted."""
    if not request.user.is_authenticated:
        return redirect("portal:signup")
    if request.method == "POST":
        form = PhoneVerificationForm(request.POST)
        if form.is_valid():
            BorrowerProfile.objects.update_or_create(user=request.user, defaults={"phone_verified": True})
            return redirect("portal:choose_office")
    else:
        form = PhoneVerificationForm()
    return render(request, "portal/auth/verify_phone.html", {"form": form})


def choose_office(request: HttpRequest) -> HttpResponse:
    """Select a help office to finish onboarding."""
    if not request.user.is_authenticated:
        return redirect("portal:signup")
    profile, _ = BorrowerProfile.objects.get_or_create(user=request.user)
    if not profile.phone_verified:
        return redirect("portal:verify_phone")
    if request.method == "POST":
        form = HelpOfficeForm(request.POST)
        if form.is_valid():
            profile.help_office = form.cleaned_data["office"]
            profile.save(update_fields=["help_office", "updated_at"])
            return redirect("portal:dashboard")
    else:
        form = HelpOfficeForm()
    return render(request, "portal/auth/choose_office.html", {"form": form, "offices": HelpOffice.objects.all()})
