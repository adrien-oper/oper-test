"""Journey: the dashboard's actions must lead somewhere that works.

Two dead ends were reported on the live dashboard: "Review and apply" on a
draft simulation bounced straight back to the dashboard (the recap rejects a
non-completed simulation), so the button looked dead; and the application card
under "Applications" was plain text with no link, so the borrower could not
open their submitted application. Each state now gets a working action.
"""

from decimal import Decimal

import pytest
from playwright.sync_api import Page, expect

from portal.models import Application, IncomeLine, Simulation

pytestmark = pytest.mark.e2e


def _completed(user):
    simulation = Simulation.objects.create(user=user, property_price=Decimal(300000), own_funds=Decimal(70000))
    IncomeLine.objects.create(simulation=simulation, monthly_amount=Decimal(6000))
    simulation.complete()
    simulation.save()
    return simulation


def test_draft_simulation_does_not_offer_a_dead_apply_button(page: Page, live_url, log_in, make_user):
    user = make_user()
    Simulation.objects.create(user=user)  # draft — never completed
    page.context.clear_cookies()
    log_in()

    page.goto(f"{live_url}/dashboard/")
    expect(page.get_by_role("link", name="Continue simulation")).to_be_visible()
    expect(page.get_by_role("link", name="Review and apply")).to_have_count(0)


def test_application_card_is_clickable_to_its_detail(page: Page, live_url, log_in, make_user):
    user = make_user()
    application = Application.create_from_simulation(_completed(user))
    page.context.clear_cookies()
    log_in()

    page.goto(f"{live_url}/dashboard/")
    page.click(f"a[href='/application/{application.pk}/']")

    expect(page).to_have_url(f"{live_url}/application/{application.pk}/")
    expect(page.get_by_role("heading", name=f"Application #{application.reference}")).to_be_visible()
