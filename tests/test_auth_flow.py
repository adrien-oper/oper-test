"""Tests for the sign-up / onboarding flow and simulation claiming."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from portal import wizard
from portal.models import HelpOffice, Simulation

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def office(db):
    return HelpOffice.objects.create(name="Central", city="Brussels")


class TestSignup:
    def test_signup_page_renders(self, client):
        response = client.get(reverse("portal:signup"))
        assert response.status_code == 200
        assert b"Sign up" in response.content

    def test_signup_creates_user_and_logs_in(self, client):
        response = client.post(
            reverse("portal:signup"),
            {"email": "ada@example.com", "password": "Str0ng!pass99", "accept_terms": "on", "accept_privacy": "on"},
        )
        assert response.status_code == 302
        assert response.url == reverse("portal:verify_phone")
        assert User.objects.filter(username="ada@example.com").exists()

    def test_signup_requires_consent(self, client):
        response = client.post(
            reverse("portal:signup"),
            {"email": "ada@example.com", "password": "Str0ng!pass99"},
        )
        assert response.status_code == 200
        assert not User.objects.exists()

    def test_signup_rejects_weak_password(self, client):
        response = client.post(
            reverse("portal:signup"),
            {"email": "ada@example.com", "password": "1234", "accept_terms": "on", "accept_privacy": "on"},
        )
        assert response.status_code == 200
        assert not User.objects.exists()

    def test_signup_rejects_duplicate_email(self, client):
        User.objects.create_user(username="ada@example.com", password="Str0ng!pass99")
        response = client.post(
            reverse("portal:signup"),
            {"email": "ada@example.com", "password": "Str0ng!pass99", "accept_terms": "on", "accept_privacy": "on"},
        )
        assert response.status_code == 200

    def test_signup_claims_session_simulation(self, client):
        client.post(reverse("portal:simulation_step", kwargs={"slug": "purpose"}), {"purpose": "buy"})
        sim_id = client.session[wizard.SIMULATION_SESSION_KEY]
        assert Simulation.objects.get(pk=sim_id).user is None

        client.post(
            reverse("portal:signup"),
            {"email": "ada@example.com", "password": "Str0ng!pass99", "accept_terms": "on", "accept_privacy": "on"},
        )
        assert Simulation.objects.get(pk=sim_id).user is not None


class TestPhoneAndOffice:
    def _signup(self, client):
        client.post(
            reverse("portal:signup"),
            {"email": "ada@example.com", "password": "Str0ng!pass99", "accept_terms": "on", "accept_privacy": "on"},
        )

    def test_verify_phone_requires_login(self, client):
        response = client.get(reverse("portal:verify_phone"))
        assert response.status_code == 302

    def test_verify_phone_accepts_stub_code(self, client):
        self._signup(client)
        response = client.post(reverse("portal:verify_phone"), {"phone_number": "+32470123456", "code": "123456"})
        assert response.status_code == 302
        assert response.url == reverse("portal:choose_office")

    def test_verify_phone_rejects_non_digit_code(self, client):
        self._signup(client)
        response = client.post(reverse("portal:verify_phone"), {"phone_number": "+32470123456", "code": "abcdef"})
        assert response.status_code == 200

    def test_verify_phone_requires_a_code(self, client):
        self._signup(client)
        response = client.post(reverse("portal:verify_phone"), {"phone_number": "+32470123456"})
        assert response.status_code == 200  # missing code re-displays the form

    def test_choose_office_requires_phone_verification(self, client, office):
        self._signup(client)  # signed in but phone not verified
        response = client.get(reverse("portal:choose_office"))
        assert response.status_code == 302
        assert response.url == reverse("portal:verify_phone")

    def test_choose_office_blocks_post_without_verification(self, client, office):
        self._signup(client)
        response = client.post(reverse("portal:choose_office"), {"office": office.pk})
        assert response.status_code == 302
        assert response.url == reverse("portal:verify_phone")
        assert "help_office_id" not in client.session

    def test_choose_office_requires_login(self, client):
        response = client.get(reverse("portal:choose_office"))
        assert response.status_code == 302

    def _verify_phone(self, client):
        client.post(reverse("portal:verify_phone"), {"phone_number": "+32470123456", "code": "123456"})

    def test_choose_office_renders_after_verification(self, client, office):
        self._signup(client)
        self._verify_phone(client)
        response = client.get(reverse("portal:choose_office"))
        assert response.status_code == 200

    def test_choose_office_lands_on_dashboard(self, client, office):
        self._signup(client)
        self._verify_phone(client)
        response = client.post(reverse("portal:choose_office"), {"office": office.pk})
        assert response.status_code == 302
        assert response.url == reverse("portal:dashboard")
        assert client.session["help_office_id"] == office.pk


class TestDashboard:
    def test_dashboard_requires_login(self, client):
        response = client.get(reverse("portal:dashboard"))
        assert response.status_code == 302

    def test_dashboard_lists_simulations(self, client):
        user = User.objects.create_user(username="ada@example.com", password="Str0ng!pass99")
        Simulation.objects.create(user=user)
        client.force_login(user)
        response = client.get(reverse("portal:dashboard"))
        assert response.status_code == 200
        assert b"Simulations" in response.content

    def test_dashboard_query_count_is_flat_in_simulations(self, client, django_assert_max_num_queries):
        from decimal import Decimal  # noqa: PLC0415

        from portal.models import IncomeLine  # noqa: PLC0415

        user = User.objects.create_user(username="ada@example.com", password="Str0ng!pass99")
        for _ in range(5):
            sim = Simulation.objects.create(user=user, property_price=Decimal(300000))
            IncomeLine.objects.create(simulation=sim, monthly_amount=Decimal(5000))
        client.force_login(user)
        with django_assert_max_num_queries(8):
            response = client.get(reverse("portal:dashboard"))
        assert response.status_code == 200
