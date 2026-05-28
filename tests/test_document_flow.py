"""Document upload, the analysis task driving the FSM, and the detail view."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from portal.models import Application, Document, DocumentState, IncomeLine, Simulation
from portal.tasks import run_document_analysis

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="ada@example.com", password="Str0ng!pass99")


@pytest.fixture
def application(user):
    sim = Simulation.objects.create(user=user, property_price=Decimal(300000))
    IncomeLine.objects.create(simulation=sim, monthly_amount=Decimal(6000))
    sim.complete()
    sim.save()
    app = Application.create_from_simulation(sim)
    app.first_name = "Ada"
    app.last_name = "Lovelace"
    app.national_number = "92052812928"
    app.save()
    return app


def _upload(application, name="payslip.pdf", content=b"Ada Lovelace 92052812928"):
    return Document.objects.create(
        application=application,
        file=SimpleUploadedFile(name, content),
        original_filename=name,
    )


class TestUploadView:
    def test_upload_creates_document_and_redirects(self, client, user, application, mocker):
        client.force_login(user)
        mocker.patch("portal.views.document.analyze_document_task")
        response = client.post(
            reverse("portal:upload_document", kwargs={"pk": application.pk}),
            {"kind": "payslip", "file": SimpleUploadedFile("payslip.pdf", b"data")},
        )
        assert response.status_code == 302
        document = Document.objects.get(application=application)
        assert document.state == DocumentState.UPLOADED

    def test_upload_requires_ownership(self, client, application):
        other = User.objects.create_user(username="eve@example.com", password="Str0ng!pass99")
        client.force_login(other)
        response = client.get(reverse("portal:upload_document", kwargs={"pk": application.pk}))
        assert response.status_code == 404

    def test_detail_renders(self, client, user, application):
        client.force_login(user)
        document = _upload(application)
        response = client.get(reverse("portal:document_detail", kwargs={"pk": document.pk}))
        assert response.status_code == 200


class TestAnalysisTask:
    @pytest.fixture(autouse=True)
    def _stub_mode(self, settings):
        settings.AI_ANALYSIS_ENABLED = False

    def test_task_drives_document_to_analyzed(self, application):
        document = _upload(application)
        run_document_analysis(document.pk)
        document = Document.objects.get(pk=document.pk)
        assert document.state == DocumentState.ANALYZED
        assert document.analysis.is_stub is True

    def test_task_flags_on_mismatch(self, application, mocker):
        document = _upload(application)
        mocker.patch(
            "portal.tasks.analyze_document",
            return_value=mocker.Mock(
                detected_kind="payslip",
                summary="s",
                extracted_fields={"national_number": "0"},
                mismatches=["national_number mismatch"],
                is_stub=True,
                model_used="stub",
            ),
        )
        run_document_analysis(document.pk)
        document = Document.objects.get(pk=document.pk)
        assert document.state == DocumentState.FLAGGED

    def test_task_fails_gracefully_on_analyzer_error(self, application, mocker):
        document = _upload(application)
        mocker.patch("portal.tasks.analyze_document", side_effect=RuntimeError("boom"))
        run_document_analysis(document.pk)
        document = Document.objects.get(pk=document.pk)
        assert document.state == DocumentState.FAILED

    def test_task_is_idempotent(self, application):
        document = _upload(application)
        run_document_analysis(document.pk)
        run_document_analysis(document.pk)  # second run is a no-op
        document = Document.objects.get(pk=document.pk)
        assert document.state == DocumentState.ANALYZED

    def test_task_ignores_missing_document(self):
        run_document_analysis(999999)  # must not raise
