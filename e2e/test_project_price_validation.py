"""Journey: the project step must reject a non-positive property price.

A property price drives the whole feasibility report (purchase costs, total
project cost, loan amount). A zero or negative price is nonsensical and yields
a meaningless report — a "within reach" mortgage on a property that costs
nothing or less than nothing. The project step must reject it and keep the
visitor on the form rather than advancing.
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def _to_project_step(page: Page, live_url: str) -> None:
    page.goto(live_url)
    page.check("input[name=purpose][value=buy]")
    page.click("button[type=submit]:has-text('Next')")
    page.check("input[name=borrower_count][value='1']")
    page.click("button[type=submit]:has-text('Next')")
    expect(page.get_by_role("heading", name="Project details")).to_be_visible()


@pytest.mark.parametrize("price", ["-100", "0"])
def test_project_step_rejects_non_positive_price(page: Page, live_url, price):
    _to_project_step(page, live_url)

    page.fill("input[name=property_price]", price)
    page.click("button[type=submit]:has-text('Next')")

    # Rejected: still on the project step, contribution step not reached.
    expect(page.get_by_role("heading", name="Project details")).to_be_visible()
    expect(page).not_to_have_url(f"{live_url}/simulation/contribution/")
