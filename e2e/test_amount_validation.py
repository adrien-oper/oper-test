"""Journey: wizard money and count fields must reject negative input.

Only the property price had a non-positive guard. Own funds, income, expense
and dependants accepted negative numbers, which were then persisted and fed
into the affordability maths and the application recap — a borrower could claim
a negative down payment or negative income. The client now sets ``min=0`` and,
more importantly, the server rejects a negative value even when the request is
forged past the browser, keeping the visitor on the form rather than advancing.
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def _to_contribution_step(page: Page, live_url: str) -> None:
    page.goto(live_url)
    page.check("input[name=purpose][value=buy]")
    page.click("button[type=submit]:has-text('Next')")
    page.check("input[name=borrower_count][value='1']")
    page.click("button[type=submit]:has-text('Next')")
    page.fill("input[name=property_price]", "300000")
    page.click("button[type=submit]:has-text('Next')")
    expect(page.get_by_role("heading", name="Your contribution")).to_be_visible()


def test_contribution_step_rejects_negative_own_funds(page: Page, live_url):
    _to_contribution_step(page, live_url)

    # Forge the POST past the client-side ``min`` to prove the server guards it.
    csrf = page.evaluate("document.querySelector('[name=csrfmiddlewaretoken]').value")
    response = page.request.post(
        f"{live_url}/simulation/contribution/",
        form={"csrfmiddlewaretoken": csrf, "own_funds": "-5000"},
    )

    # Rejected (re-rendered form), not a redirect on to the income step.
    assert response.status == 200
    assert "/simulation/income/" not in response.url

    # And the browser blocks it client-side too: still on the contribution step.
    page.fill("input[name=own_funds]", "-5000")
    page.click("button[type=submit]:has-text('Next')")
    expect(page.get_by_role("heading", name="Your contribution")).to_be_visible()
    expect(page).not_to_have_url(f"{live_url}/simulation/income/")
