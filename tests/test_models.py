"""String representations and small derived properties on the domain models."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from portal.models import Application, BorrowerProfile, Document, DocumentAnalysis, HelpOffice, IncomeLine, Simulation

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="ada@example.com", password="Str0ng!pass99")


class TestBorrowerProfile:
    def test_str_reports_verification(self, user):
        profile = BorrowerProfile.objects.create(user=user, phone_verified=True)
        assert "verified=True" in str(profile)

    def test_onboarding_complete_needs_office_and_verification(self, user):
        office = HelpOffice.objects.create(name="Central", city="Brussels")
        profile = BorrowerProfile.objects.create(user=user, phone_verified=True)
        assert profile.onboarding_complete is False
        profile.help_office = office
        assert profile.onboarding_complete is True


class TestDocumentStrings:
    def test_document_str_uses_filename_and_state(self, user):
        sim = Simulation.objects.create(user=user, property_price=Decimal(300000))
        IncomeLine.objects.create(simulation=sim, monthly_amount=Decimal(6000))
        sim.complete()
        sim.save()
        app = Application.create_from_simulation(sim)
        document = Document.objects.create(
            application=app, file=SimpleUploadedFile("payslip.pdf", b"x"), original_filename="payslip.pdf"
        )
        analysis = DocumentAnalysis.objects.create(document=document, detected_kind="payslip", mismatches=["x"])
        assert "payslip.pdf" in str(document)
        assert "stub" in str(analysis)
        assert analysis.has_mismatches is True
