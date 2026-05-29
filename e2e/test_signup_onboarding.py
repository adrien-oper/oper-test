"""Journey: sign up, verify phone, choose an office, land on the dashboard.

A visitor starts an anonymous simulation, then signs up. Sign-up claims the
session's simulation onto the new account, so the dashboard shows it. Phone
verification accepts any 6-digit code (it is stubbed) and choosing a help
office finishes onboarding.
"""

import pytest
from playwright.sync_api import Page, expect

from portal.models import HelpOffice, Simulation

pytestmark = pytest.mark.e2e


def test_signup_through_to_dashboard_claims_the_simulation(page: Page, live_url, seeded_offices):
    office = HelpOffice.objects.first()  # provided by the seed migration's data function

    # Start an anonymous simulation so sign-up has something to claim.
    page.goto(live_url)
    page.check("input[name=purpose][value=buy]")
    page.click("button[type=submit]:has-text('Next')")
    assert Simulation.objects.filter(user__isnull=True).count() == 1

    page.goto(f"{live_url}/signup/")
    page.fill("#id_email", "ada@example.com")
    page.fill("#id_password", "Str0ng!pass99")
    page.check("#id_accept_terms")
    page.check("#id_accept_privacy")
    page.click("button:has-text('Agree')")

    expect(page.get_by_role("heading", name="Enter phone number")).to_be_visible()
    page.fill("#id_phone_number", "+32470123456")
    page.fill("#id_code", "123456")
    page.click("button:has-text('Continue')")

    expect(page.get_by_role("heading", name="Choose a help office")).to_be_visible()
    page.select_option("#id_office", label=str(office))
    page.click("button:has-text('Finish')")

    expect(page).to_have_url(f"{live_url}/dashboard/")
    expect(page.get_by_role("heading", name="Simulations")).to_be_visible()

    assert Simulation.objects.filter(user__username="ada@example.com").count() == 1
    assert not Simulation.objects.filter(user__isnull=True).exists()
