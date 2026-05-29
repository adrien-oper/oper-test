"""Journey: turn a completed simulation into a submitted application.

A signed-in borrower reviews a completed simulation, converts it to an
application, fills the applicant details and submits. Submission runs the
guarded ``submit_for_review`` transition, so the application lands in
``under_review``.
"""

from decimal import Decimal

import pytest
from playwright.sync_api import Page, expect

from portal.models import Application, ApplicationState, IncomeLine, Simulation

pytestmark = pytest.mark.e2e


@pytest.fixture
def completed_simulation(make_user):
    user = make_user()
    simulation = Simulation.objects.create(user=user, property_price=Decimal(300000), own_funds=Decimal(70000))
    IncomeLine.objects.create(simulation=simulation, monthly_amount=Decimal(6000))
    simulation.complete()
    simulation.save()
    return simulation


def test_apply_convert_and_submit_for_review(page: Page, live_url, log_in, completed_simulation):
    log_in()

    page.goto(f"{live_url}/dashboard/")
    page.click("a:has-text('Review and apply')")

    expect(page.get_by_role("heading", name="Review your simulation")).to_be_visible()
    page.click("button:has-text('Convert to application')")

    expect(page.get_by_role("heading", name="Your application")).to_be_visible()
    page.fill("#id_first_name", "Ada")
    page.fill("#id_last_name", "Lovelace")
    page.fill("#id_national_number", "92052812928")
    page.click("button:has-text('Submit loan request')")

    expect(page.locator(".pill")).to_contain_text("Under review")

    application = Application.objects.get(simulation=completed_simulation)
    assert application.state == ApplicationState.UNDER_REVIEW
