"""Admin changelists, change pages, FSM transitions and query-count guards."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from portal.models import (
    Application,
    ApplicationState,
    BorrowerProfile,
    Document,
    DocumentAnalysis,
    HelpOffice,
    IncomeLine,
    Simulation,
)

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def staff(db):
    return User.objects.create_superuser(username="staff@example.com", password="Str0ng!pass99")


@pytest.fixture
def application(db):
    owner = User.objects.create_user(username="ada@example.com", password="Str0ng!pass99")
    sim = Simulation.objects.create(user=owner, property_price=Decimal(300000))
    IncomeLine.objects.create(simulation=sim, monthly_amount=Decimal(6000))
    sim.complete()
    sim.save()
    app = Application.create_from_simulation(sim)
    app.first_name = "Ada"
    app.last_name = "Lovelace"
    app.national_number = "92052812928"
    app.save()
    return app


@pytest.fixture
def document(application):
    doc = Document.objects.create(
        application=application,
        file=SimpleUploadedFile("payslip.pdf", b"Ada Lovelace"),
        original_filename="payslip.pdf",
    )
    DocumentAnalysis.objects.create(document=doc, detected_kind="payslip", summary="A payslip.")
    return doc


_CHANGELISTS = [
    "portal_helpoffice",
    "portal_borrowerprofile",
    "portal_simulation",
    "portal_application",
    "portal_document",
    "portal_documentanalysis",
]


class TestChangelists:
    @pytest.mark.parametrize("route", _CHANGELISTS)
    def test_changelist_renders(self, client, staff, application, document, route):
        BorrowerProfile.objects.create(user=application.user, help_office=HelpOffice.objects.create(name="C", city="B"))
        client.force_login(staff)
        response = client.get(reverse(f"admin:{route}_changelist"))
        assert response.status_code == 200

    def test_application_changelist_query_count_flat_across_rows(self, client, staff, django_assert_max_num_queries):
        owner = User.objects.create_user(username="multi@example.com", password="Str0ng!pass99")
        for _ in range(5):
            sim = Simulation.objects.create(user=owner, property_price=Decimal(300000))
            IncomeLine.objects.create(simulation=sim, monthly_amount=Decimal(6000))
            sim.complete()
            sim.save()
            Application.create_from_simulation(sim)
        client.force_login(staff)
        with django_assert_max_num_queries(12):
            response = client.get(reverse("admin:portal_application_changelist"))
        assert response.status_code == 200


class TestChangePages:
    def test_application_change_page_renders(self, client, staff, application):
        client.force_login(staff)
        response = client.get(reverse("admin:portal_application_change", args=[application.pk]))
        assert response.status_code == 200

    def test_document_change_page_renders(self, client, staff, document):
        client.force_login(staff)
        response = client.get(reverse("admin:portal_document_change", args=[document.pk]))
        assert response.status_code == 200

    def test_simulation_change_page_renders(self, client, staff, application):
        client.force_login(staff)
        response = client.get(reverse("admin:portal_simulation_change", args=[application.simulation.pk]))
        assert response.status_code == 200


class TestApplicationFsmAdmin:
    def _under_review(self, application):
        application.submit_for_review()
        return application

    def test_change_page_exposes_decide_transitions(self, client, staff, application):
        self._under_review(application)
        client.force_login(staff)
        response = client.get(reverse("admin:portal_application_change", args=[application.pk]))
        assert b"_fsm_transition_to" in response.content

    def test_submitted_app_exposes_start_review_button(self, client, staff, application):
        application.submit()  # -> SUBMITTED (the state a reviewer opens review from)
        application.save()
        client.force_login(staff)
        response = client.get(reverse("admin:portal_application_change", args=[application.pk]))
        assert b'value="start_review"' in response.content

    def test_start_review_transition_via_admin_post(self, client, staff, application):
        application.submit()  # -> SUBMITTED
        application.save()
        client.force_login(staff)
        client.post(
            reverse("admin:portal_application_change", args=[application.pk]),
            self._change_form_data(application, _fsm_transition_to="start_review"),
        )
        assert Application.objects.get(pk=application.pk).state == ApplicationState.UNDER_REVIEW

    def _change_form_data(self, application, **overrides):
        data = {
            "first_name": application.first_name,
            "last_name": application.last_name,
            "national_number": application.national_number,
            "current_address": application.current_address,
            "employment_status": application.employment_status,
            "employer_name": application.employer_name,
            "decision_note": application.decision_note,
            "documents-TOTAL_FORMS": "0",
            "documents-INITIAL_FORMS": "0",
            "documents-MIN_NUM_FORMS": "0",
            "documents-MAX_NUM_FORMS": "1000",
        }
        data.update(overrides)
        return data

    def test_reviewer_can_approve_via_admin(self, client, staff, application):
        self._under_review(application)
        client.force_login(staff)
        client.post(
            reverse("admin:portal_application_change", args=[application.pk]),
            self._change_form_data(application, _fsm_transition_to="approve"),
        )
        assert Application.objects.get(pk=application.pk).state == ApplicationState.APPROVED

    def _reviewer_without_decide(self):
        reviewer = User.objects.create_user(username="weak@example.com", password="Str0ng!pass99", is_staff=True)
        app_perms = Permission.objects.filter(content_type=ContentType.objects.get_for_model(Application)).exclude(
            codename="decide_application"
        )
        reviewer.user_permissions.add(*app_perms)
        return reviewer

    def test_decide_transition_hidden_without_permission(self, client, application):
        self._under_review(application)
        client.force_login(self._reviewer_without_decide())
        response = client.get(reverse("admin:portal_application_change", args=[application.pk]))
        assert b'value="approve"' not in response.content

    def test_forged_decide_post_is_rejected_without_permission(self, client, application):
        self._under_review(application)
        client.force_login(self._reviewer_without_decide())
        response = client.post(
            reverse("admin:portal_application_change", args=[application.pk]),
            self._change_form_data(application, _fsm_transition_to="approve"),
        )
        assert response.status_code == 403
        assert Application.objects.get(pk=application.pk).state == ApplicationState.UNDER_REVIEW

    def test_admin_approve_preserves_typed_decision_note(self, client, staff, application):
        self._under_review(application)
        client.force_login(staff)
        client.post(
            reverse("admin:portal_application_change", args=[application.pk]),
            self._change_form_data(application, decision_note="Income verified.", _fsm_transition_to="approve"),
        )
        decided = Application.objects.get(pk=application.pk)
        assert decided.state == ApplicationState.APPROVED
        assert decided.decision_note == "Income verified."
