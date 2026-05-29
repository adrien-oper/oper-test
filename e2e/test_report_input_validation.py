"""Journey: the feasibility report must not 500 on hostile slider input.

The report re-runs the affordability maths from query parameters
(``own_funds``, ``duration``) so the sliders can preview alternative
down-payments without persisting them. Those parameters are visitor-supplied:
anyone can edit the URL. A value that parses as a Decimal but is not a finite
number (``NaN``, ``Infinity``, an exponent that overflows the Decimal context)
must be rejected and ignored, not fed into the arithmetic where it raises and
returns a 500.
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def _walk_to_report(page: Page, live_url: str) -> None:
    page.goto(live_url)
    page.check("input[name=purpose][value=buy]")
    page.click("button[type=submit]:has-text('Next')")
    page.check("input[name=borrower_count][value='1']")
    page.click("button[type=submit]:has-text('Next')")
    page.fill("input[name=property_price]", "300000")
    page.click("button[type=submit]:has-text('Next')")
    page.fill("input[name=own_funds]", "60000")
    page.click("button[type=submit]:has-text('Next')")
    page.fill("#rows-wrap input[name=monthly_amount]", "6000")
    page.click("button:has-text('Add income')")
    expect(page.locator("#rows-wrap .row-item")).to_have_count(1)
    page.click("button[type=submit]:has-text('Next')")  # expenses
    page.click("button[type=submit]:has-text('Next')")  # personal
    page.click("button[type=submit]:has-text('Next')")  # report
    expect(page.locator("#report-card")).to_contain_text("Loan amount")


@pytest.mark.parametrize("own_funds", ["NaN", "Infinity", "1e10000", "sNaN"])
def test_report_ignores_non_finite_own_funds(page: Page, live_url, own_funds):
    _walk_to_report(page, live_url)

    response = page.request.get(f"{live_url}/simulation/report/?own_funds={own_funds}")

    assert response.status == 200, f"own_funds={own_funds!r} returned {response.status}"
    assert "Loan amount" in response.text()
