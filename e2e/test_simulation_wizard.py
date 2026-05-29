"""Journey: the anonymous simulation wizard end to end.

Walks a visitor from the project-purpose step through to the feasibility
report, exercising the two pieces of live interactivity along the way: the
HTMX add-income-row that swaps ``#rows-wrap``, and the report slider whose
``input`` event re-fetches and re-renders the report card.
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def _next(page: Page) -> None:
    page.click("button[type=submit]:has-text('Next')")


def test_wizard_runs_through_to_the_report(page: Page, live_url):
    page.goto(live_url)
    expect(page.get_by_role("heading", name="Welcome to your home journey!")).to_be_visible()

    page.check("input[name=purpose][value=buy]")
    _next(page)

    expect(page.get_by_role("heading", name="Who is borrowing?")).to_be_visible()
    page.check("input[name=borrower_count][value='1']")
    _next(page)

    expect(page.get_by_role("heading", name="Project details")).to_be_visible()
    page.fill("input[name=property_price]", "300000")
    _next(page)

    expect(page.get_by_role("heading", name="Your contribution")).to_be_visible()
    page.fill("input[name=own_funds]", "60000")
    _next(page)

    expect(page.get_by_role("heading", name="Your income")).to_be_visible()
    page.fill("#rows-wrap input[name=monthly_amount]", "6000")
    page.click("button:has-text('Add income')")
    expect(page.locator("#rows-wrap .row-item")).to_have_count(1)
    expect(page.locator("#rows-wrap")).to_contain_text("6000")
    _next(page)

    expect(page.get_by_role("heading", name="Your expenses")).to_be_visible()
    _next(page)

    expect(page.get_by_role("heading", name="Personal details")).to_be_visible()
    _next(page)

    expect(page.get_by_role("heading", name="Your simulation report")).to_be_visible()
    expect(page.locator("#report-card")).to_contain_text("Loan amount")


def test_report_slider_recomputes_the_card(page: Page, live_url):
    page.goto(live_url)
    page.check("input[name=purpose][value=buy]")
    _next(page)
    page.check("input[name=borrower_count][value='1']")
    _next(page)
    page.fill("input[name=property_price]", "300000")
    _next(page)
    page.fill("input[name=own_funds]", "20000")
    _next(page)
    page.fill("#rows-wrap input[name=monthly_amount]", "6000")
    page.click("button:has-text('Add income')")
    expect(page.locator("#rows-wrap .row-item")).to_have_count(1)
    _next(page)  # expenses
    _next(page)  # personal
    _next(page)  # report

    card = page.locator("#report-card")
    expect(card).to_contain_text("Monthly payment")
    before = card.inner_text()

    duration = page.locator("input[type=range][name=duration]")
    duration.fill("10")
    duration.dispatch_event("input")

    expect(page.locator("#report-card")).not_to_have_text(before)
    expect(page.locator("#report-card")).to_contain_text("10 years")
