"""Journey: upload a supporting document and watch its analysis resolve.

Two terminal outcomes are covered. The happy path uploads a ``.txt`` file and
runs the (stubbed, offline) analysis, which echoes the application's own data
and so settles on ``analyzed``. The mismatch path seeds an analysis whose
extracted fields disagree with the application and drives the document to
``flagged`` — the stub never mismatches on its own, so the discrepancy is
arranged directly.
"""

import re
from decimal import Decimal

import pytest
from playwright.sync_api import Page, expect

from portal.models import Application, Document, DocumentAnalysis, DocumentState, IncomeLine, Simulation
from portal.tasks import run_document_analysis

pytestmark = pytest.mark.e2e


@pytest.fixture
def application(make_user):
    user = make_user()
    simulation = Simulation.objects.create(user=user, property_price=Decimal(300000))
    IncomeLine.objects.create(simulation=simulation, monthly_amount=Decimal(6000))
    simulation.complete()
    simulation.save()
    application = Application.create_from_simulation(simulation)
    application.first_name = "Ada"
    application.last_name = "Lovelace"
    application.national_number = "92052812928"
    application.save()
    return application


def _upload_txt(page: Page, live_url, application, tmp_path):
    upload = tmp_path / "payslip.txt"
    upload.write_text("Ada Lovelace 92052812928\nGross monthly income 6000")

    page.goto(f"{live_url}/application/{application.pk}/")
    page.click("a:has-text('Upload a document')")
    expect(page.get_by_role("heading", name="Upload a document")).to_be_visible()

    page.select_option("#id_kind", value="payslip")
    page.set_input_files("#id_file", str(upload))
    page.click("button:has-text('Complete upload')")

    expect(page).to_have_url(re.compile(r"/document/\d+/$"))
    return Document.objects.get(application=application)


def test_upload_txt_resolves_to_analyzed(page: Page, live_url, log_in, application, tmp_path):
    log_in()
    document = _upload_txt(page, live_url, application, tmp_path)
    assert document.state == DocumentState.UPLOADED

    run_document_analysis(document.pk)
    assert Document.objects.get(pk=document.pk).state == DocumentState.ANALYZED

    page.reload()
    expect(page.locator("#doc-status .pill")).to_contain_text("Analyzed")
    expect(page.locator("#doc-status")).not_to_have_attribute("hx-trigger", "every 2s")


def test_upload_with_mismatch_resolves_to_flagged(page: Page, live_url, log_in, application, tmp_path):
    log_in()
    document = _upload_txt(page, live_url, application, tmp_path)

    DocumentAnalysis.objects.create(
        document=document,
        detected_kind="payslip",
        summary="Name on the document does not match the application.",
        extracted_fields={"full_name": "Someone Else"},
        mismatches=["Document full_name 'Someone Else' does not match application 'Ada Lovelace'."],
        is_stub=True,
        model_used="stub",
    )
    document.start_analysis()
    document.save()
    document.flag()
    document.save()

    page.reload()
    expect(page.locator("#doc-status .pill")).to_contain_text("Flagged")
    expect(page.locator("#doc-status")).to_contain_text("does not match application")
