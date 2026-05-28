"""Dashboard — the borrower's home after sign-in.

Fleshed out in the dashboard/application chunk. For now it lists the user's
simulations so the post-login and apply routes have a real destination.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """Show the signed-in user's simulations and applications."""
    return render(
        request,
        "portal/dashboard.html",
        {
            "simulations": request.user.simulations.all(),
            "applications": request.user.applications.all(),
        },
    )
