"""Apply flow: recap, atomic conversion, multi-step form, submission."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from portal.models import Application, ApplicationState, IncomeLine, Simulation, SimulationState

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="ada@example.com", password="Str0ng!pass99")


@pytest.fixture
def completed_simulation(user):
    sim = Simulation.objects.create(user=user, property_price=Decimal(300000), own_funds=Decimal(70000))
    IncomeLine.objects.create(simulation=sim, monthly_amount=Decimal(6000))
    sim.complete()
    sim.save()
    return sim


class TestApplyRecap:
    def test_recap_renders(self, client, user, completed_simulation):
        client.force_login(user)
        response = client.get(reverse("portal:apply_recap", kwargs={"pk": completed_simulation.pk}))
        assert response.status_code == 200
        assert b"Review your simulation" in response.content

    def test_recap_requires_ownership(self, client, completed_simulation):
        other = User.objects.create_user(username="eve@example.com", password="Str0ng!pass99")
        client.force_login(other)
        response = client.get(reverse("portal:apply_recap", kwargs={"pk": completed_simulation.pk}))
        assert response.status_code == 404

    def test_recap_redirects_when_already_converted(self, client, user, completed_simulation):
        client.force_login(user)
        application = Application.create_from_simulation(completed_simulation)
        response = client.get(reverse("portal:apply_recap", kwargs={"pk": completed_simulation.pk}))
        assert response.status_code == 302
        assert response.url == reverse("portal:application_detail", kwargs={"pk": application.pk})


class TestConversion:
    def test_convert_creates_application_and_transitions(self, client, user, completed_simulation):
        client.force_login(user)
        response = client.post(reverse("portal:convert_simulation", kwargs={"pk": completed_simulation.pk}))
        application = Application.objects.get(simulation=completed_simulation)
        assert response.url == reverse("portal:application_form", kwargs={"pk": application.pk})
        assert Simulation.objects.get(pk=completed_simulation.pk).state == SimulationState.CONVERTED

    def test_convert_is_idempotent(self, client, user, completed_simulation):
        client.force_login(user)
        client.post(reverse("portal:convert_simulation", kwargs={"pk": completed_simulation.pk}))
        client.post(reverse("portal:convert_simulation", kwargs={"pk": completed_simulation.pk}))
        assert Application.objects.filter(simulation=completed_simulation).count() == 1


class TestApplicationForm:
    def _application(self, completed_simulation):
        return Application.create_from_simulation(completed_simulation)

    def test_submit_with_details_moves_to_under_review(self, client, user, completed_simulation):
        client.force_login(user)
        application = self._application(completed_simulation)
        response = client.post(
            reverse("portal:application_form", kwargs={"pk": application.pk}),
            {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "national_number": "92052812928",
                "employment_status": "employee",
            },
        )
        assert response.url == reverse("portal:application_detail", kwargs={"pk": application.pk})
        assert Application.objects.get(pk=application.pk).state == ApplicationState.UNDER_REVIEW

    def test_submit_without_required_details_is_blocked(self, client, user, completed_simulation):
        client.force_login(user)
        application = self._application(completed_simulation)
        response = client.post(
            reverse("portal:application_form", kwargs={"pk": application.pk}),
            {"first_name": "", "last_name": "", "national_number": "", "employment_status": "employee"},
        )
        assert response.status_code == 302  # bounced back to the form by the guard
        assert Application.objects.get(pk=application.pk).state == ApplicationState.DRAFT

    def test_detail_renders(self, client, user, completed_simulation):
        client.force_login(user)
        application = self._application(completed_simulation)
        response = client.get(reverse("portal:application_detail", kwargs={"pk": application.pk}))
        assert response.status_code == 200
        assert application.reference.encode() in response.content
