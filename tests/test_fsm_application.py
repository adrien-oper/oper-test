"""FSM behaviour for the application lifecycle and simulation conversion."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django_fsm import TransitionNotAllowed, has_transition_perm

from portal.models import Application, ApplicationState, IncomeLine, Simulation, SimulationState

pytestmark = pytest.mark.django_db

User = get_user_model()


def _completed_simulation(user) -> Simulation:
    sim = Simulation.objects.create(user=user, property_price=Decimal(300000), own_funds=Decimal(70000))
    IncomeLine.objects.create(simulation=sim, monthly_amount=Decimal(5000))
    sim.complete()
    sim.save()
    return sim


@pytest.fixture
def user(db):
    return User.objects.create_user(username="borrower", password="pw-test-1234!")


class TestConversion:
    def test_create_from_simulation_links_and_transitions(self, user):
        sim = _completed_simulation(user)
        application = Application.create_from_simulation(sim)
        stored = Simulation.objects.get(pk=sim.pk)
        assert application.simulation_id == sim.pk
        assert application.user == user
        assert stored.state == SimulationState.CONVERTED
        assert application.state == ApplicationState.DRAFT
        assert application.reference.startswith("A")

    def test_one_application_per_simulation(self, user):
        sim = _completed_simulation(user)
        Application.create_from_simulation(sim)
        sim2 = Simulation.objects.get(pk=sim.pk)
        with pytest.raises(Exception):  # noqa: B017, PT011 — OneToOne integrity
            Application.create_from_simulation(sim2)


class TestApplicationLifecycle:
    def _draft(self, user) -> Application:
        return Application.create_from_simulation(_completed_simulation(user))

    def test_submit_requires_personal_details(self, user):
        app = self._draft(user)
        with pytest.raises(TransitionNotAllowed):
            app.submit()

    def test_full_happy_path_to_approval(self, user):
        reviewer = User.objects.create_user(username="reviewer", password="pw-test-1234!", is_staff=True)
        from django.contrib.auth.models import Permission  # noqa: PLC0415

        reviewer.user_permissions.add(Permission.objects.get(codename="decide_application"))
        reviewer = User.objects.get(pk=reviewer.pk)  # refresh perm cache

        app = self._draft(user)
        app.first_name = "Ada"
        app.last_name = "Lovelace"
        app.national_number = "92052812928"
        app.submit()
        app.save()
        assert app.state == ApplicationState.SUBMITTED
        assert app.submitted_at is not None

        app.start_review()
        app.save()
        assert app.state == ApplicationState.UNDER_REVIEW

        assert has_transition_perm(app.approve, reviewer)
        app.approve(note="looks good")
        app.save()
        assert app.state == ApplicationState.APPROVED
        assert app.decision_note == "looks good"

    def test_reject_from_review(self, user):
        app = self._draft(user)
        app.first_name = "Ada"
        app.last_name = "Lovelace"
        app.national_number = "92052812928"
        app.submit()
        app.start_review()
        app.reject(note="insufficient income")
        app.save()
        assert app.state == ApplicationState.REJECTED

    def test_cannot_approve_before_review(self, user):
        app = self._draft(user)
        with pytest.raises(TransitionNotAllowed):
            app.approve()

    def test_borrower_lacks_decide_permission(self, user):
        app = self._draft(user)
        assert has_transition_perm(app.approve, user) is False
