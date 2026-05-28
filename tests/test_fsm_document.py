"""FSM behaviour for the document analysis lifecycle."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django_fsm import TransitionNotAllowed

from portal.models import Application, Document, DocumentState, IncomeLine, Simulation

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def document(db):
    user = User.objects.create_user(username="borrower", password="pw-test-1234!")
    sim = Simulation.objects.create(user=user, property_price=Decimal(300000))
    IncomeLine.objects.create(simulation=sim, monthly_amount=Decimal(5000))
    sim.complete()
    sim.save()
    application = Application.create_from_simulation(sim)
    return Document.objects.create(
        application=application,
        file=SimpleUploadedFile("payslip.pdf", b"%PDF-1.4 fake"),
        original_filename="payslip.pdf",
    )


class TestDocumentLifecycle:
    def test_starts_uploaded(self, document):
        assert document.state == DocumentState.UPLOADED
        assert document.is_terminal is False

    def test_analyze_to_analyzed(self, document):
        document.start_analysis()
        document.save()
        assert document.state == DocumentState.ANALYZING
        document.mark_analyzed()
        document.save()
        assert document.state == DocumentState.ANALYZED
        assert document.is_terminal is True

    def test_analyze_to_flagged(self, document):
        document.start_analysis()
        document.flag()
        assert document.state == DocumentState.FLAGGED
        assert document.is_terminal is True

    def test_cannot_analyze_twice(self, document):
        document.start_analysis()
        with pytest.raises(TransitionNotAllowed):
            document.start_analysis()

    def test_fail_from_uploaded(self, document):
        document.fail()
        assert document.state == DocumentState.FAILED

    def test_fail_from_analyzing(self, document):
        document.start_analysis()
        document.fail()
        assert document.state == DocumentState.FAILED

    def test_cannot_mark_analyzed_without_analyzing(self, document):
        with pytest.raises(TransitionNotAllowed):
            document.mark_analyzed()
