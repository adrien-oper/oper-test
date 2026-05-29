"""Journey: a document the extractor cannot read ends up ``failed``.

The upload form already rejects unsupported extensions, so a file the
extractor cannot read only reaches the analysis task through a path the form
did not guard (e.g. a future ingestion route). This drives that path directly:
a document with an unreadable file type runs through the analysis task, whose
``extract_text`` raises :class:`UnsupportedDocumentError`, and the FSM lands on
``failed``. The detail page then shows the terminal failed state and stops
polling.
"""

from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from playwright.sync_api import Page, expect

from portal.models import Application, Document, DocumentState, IncomeLine, Simulation
from portal.tasks import run_document_analysis

pytestmark = pytest.mark.e2e


@pytest.fixture
def application(make_user):
    user = make_user()
    simulation = Simulation.objects.create(user=user, property_price=Decimal(300000))
    IncomeLine.objects.create(simulation=simulation, monthly_amount=Decimal(6000))
    simulation.complete()
    simulation.save()
    return Application.create_from_simulation(simulation)


def test_unsupported_file_resolves_to_failed(page: Page, live_url, log_in, application):
    log_in()

    document = Document.objects.create(
        application=application,
        file=SimpleUploadedFile("installer.exe", b"MZ\x90\x00binary"),
        original_filename="installer.exe",
    )

    run_document_analysis(document.pk)
    assert Document.objects.get(pk=document.pk).state == DocumentState.FAILED

    page.goto(f"{live_url}/document/{document.pk}/")
    expect(page.locator("#doc-status .pill")).to_contain_text("Analysis failed")
    expect(page.locator("#doc-status")).not_to_have_attribute("hx-trigger", "every 2s")
