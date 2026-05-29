"""Journey: onboarding must be completable on a freshly-migrated database.

Choosing a help office is a required onboarding step. The dropdown is fed
from the ``HelpOffice`` table, so a database with no offices leaves the step
with nothing to pick: the required field can never validate and the visitor is
stuck, unable to reach the dashboard.

This test deliberately does NOT create any office of its own — it relies on
migrations having seeded at least one — so it reproduces what a real visitor
hits on a fresh deploy.
"""

import pytest
from playwright.sync_api import Page, expect

from portal.models import HelpOffice

pytestmark = pytest.mark.e2e


def test_fresh_database_seeds_at_least_one_help_office(db):
    assert HelpOffice.objects.exists(), "a freshly-migrated database must seed at least one help office"


def test_onboarding_completes_without_creating_an_office(page: Page, live_url, seeded_offices):
    # No HelpOffice.objects.create(...) here on purpose: ``seeded_offices`` runs
    # the seed migration's own data function, so this exercises the real seed
    # logic the deploy depends on, not a hand-built office. (``live_server``
    # flushes migration rows between transactional tests, so the fixture
    # re-applies the idempotent seed.)
    page.goto(f"{live_url}/signup/")
    page.fill("#id_email", "fresh@example.com")
    page.fill("#id_password", "Str0ng!pass99")
    page.check("#id_accept_terms")
    page.check("#id_accept_privacy")
    page.click("button:has-text('Agree')")

    expect(page.get_by_role("heading", name="Enter phone number")).to_be_visible()
    page.fill("#id_phone_number", "+32470123456")
    page.fill("#id_code", "123456")
    page.click("button:has-text('Continue')")

    expect(page.get_by_role("heading", name="Choose a help office")).to_be_visible()
    first_office = HelpOffice.objects.first()
    page.select_option("#id_office", label=str(first_office))
    page.click("button:has-text('Finish')")

    expect(page).to_have_url(f"{live_url}/dashboard/")
