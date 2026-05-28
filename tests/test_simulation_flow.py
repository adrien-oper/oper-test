"""End-to-end tests for the anonymous simulation HTMX flow."""

import pytest
from django.urls import reverse

from portal import wizard
from portal.models import Simulation, SimulationState

pytestmark = pytest.mark.django_db


class TestWizardNavigation:
    def test_start_redirects_to_first_step(self, client):
        response = client.get(reverse("portal:simulation_start"))
        assert response.status_code == 302
        assert response.url == reverse("portal:simulation_step", kwargs={"slug": "purpose"})

    def test_start_clears_previous_session_simulation(self, client):
        session = client.session
        session[wizard.SIMULATION_SESSION_KEY] = 999
        session.save()
        client.get(reverse("portal:simulation_start"))
        assert wizard.SIMULATION_SESSION_KEY not in client.session

    def test_purpose_step_renders(self, client):
        response = client.get(reverse("portal:simulation_step", kwargs={"slug": "purpose"}))
        assert response.status_code == 200
        assert b"project purpose" in response.content.lower()

    def test_posting_purpose_creates_simulation_and_advances(self, client):
        response = client.post(reverse("portal:simulation_step", kwargs={"slug": "purpose"}), {"purpose": "buy"})
        assert response.status_code == 302
        assert response.url == reverse("portal:simulation_step", kwargs={"slug": "borrowers"})
        sim_id = client.session[wizard.SIMULATION_SESSION_KEY]
        assert Simulation.objects.get(pk=sim_id).purpose == "buy"

    def test_project_step_persists_values(self, client):
        client.post(reverse("portal:simulation_step", kwargs={"slug": "purpose"}), {"purpose": "buy"})
        client.post(
            reverse("portal:simulation_step", kwargs={"slug": "project"}),
            {"property_type": "house", "region": "flanders", "property_price": "250000", "property_usage": "own_home"},
        )
        sim = Simulation.objects.get(pk=client.session[wizard.SIMULATION_SESSION_KEY])
        assert str(sim.property_price) == "250000.00"

    def test_invalid_post_redisplays_form(self, client):
        client.post(reverse("portal:simulation_step", kwargs={"slug": "purpose"}), {"purpose": "buy"})
        response = client.post(
            reverse("portal:simulation_step", kwargs={"slug": "project"}),
            {"property_type": "house", "region": "flanders", "property_price": "not-a-number"},
        )
        assert response.status_code == 200

    def test_back_link_present_after_first_step(self, client):
        client.post(reverse("portal:simulation_step", kwargs={"slug": "purpose"}), {"purpose": "buy"})
        response = client.get(reverse("portal:simulation_step", kwargs={"slug": "borrowers"}))
        assert b"Back" in response.content


class TestFinancialSteps:
    def _begin(self, client):
        client.post(reverse("portal:simulation_step", kwargs={"slug": "purpose"}), {"purpose": "buy"})

    def test_income_step_renders(self, client):
        self._begin(client)
        response = client.get(reverse("portal:simulation_step", kwargs={"slug": "income"}))
        assert response.status_code == 200
        assert b"Your income" in response.content

    def test_add_income_line_via_htmx(self, client):
        self._begin(client)
        response = client.post(
            reverse("portal:add_income_line"),
            {"income_type": "salary", "monthly_amount": "5000"},
            headers={"hx-request": "true"},
        )
        assert response.status_code == 200
        sim = Simulation.objects.get(pk=client.session[wizard.SIMULATION_SESSION_KEY])
        assert sim.incomes.count() == 1

    def test_delete_income_line_via_htmx(self, client):
        self._begin(client)
        client.post(reverse("portal:add_income_line"), {"income_type": "salary", "monthly_amount": "5000"})
        sim = Simulation.objects.get(pk=client.session[wizard.SIMULATION_SESSION_KEY])
        line = sim.incomes.first()
        client.post(reverse("portal:delete_income_line", kwargs={"pk": line.pk}))
        assert sim.incomes.count() == 0

    def test_add_expense_line_via_htmx(self, client):
        self._begin(client)
        client.post(reverse("portal:add_expense_line"), {"expense_type": "rent", "monthly_amount": "900"})
        sim = Simulation.objects.get(pk=client.session[wizard.SIMULATION_SESSION_KEY])
        assert sim.expenses.count() == 1

    def test_delete_expense_line_via_htmx(self, client):
        self._begin(client)
        client.post(reverse("portal:add_expense_line"), {"expense_type": "rent", "monthly_amount": "900"})
        sim = Simulation.objects.get(pk=client.session[wizard.SIMULATION_SESSION_KEY])
        line = sim.expenses.first()
        client.post(reverse("portal:delete_expense_line", kwargs={"pk": line.pk}))
        assert sim.expenses.count() == 0

    def test_financial_step_post_advances(self, client):
        self._begin(client)
        response = client.post(reverse("portal:simulation_step", kwargs={"slug": "income"}))
        assert response.status_code == 302
        assert response.url == reverse("portal:simulation_step", kwargs={"slug": "expenses"})


class TestReport:
    def _ready_simulation(self, client):
        client.post(reverse("portal:simulation_step", kwargs={"slug": "purpose"}), {"purpose": "buy"})
        client.post(
            reverse("portal:simulation_step", kwargs={"slug": "project"}),
            {"property_type": "house", "region": "flanders", "property_price": "300000", "property_usage": "own_home"},
        )
        client.post(reverse("portal:add_income_line"), {"income_type": "salary", "monthly_amount": "6000"})

    def test_report_without_simulation_redirects(self, client):
        response = client.get(reverse("portal:simulation_step", kwargs={"slug": "report"}))
        assert response.status_code == 302

    def test_report_completes_simulation(self, client):
        self._ready_simulation(client)
        response = client.get(reverse("portal:simulation_step", kwargs={"slug": "report"}))
        assert response.status_code == 200
        sim = Simulation.objects.get(pk=client.session[wizard.SIMULATION_SESSION_KEY])
        assert sim.state == SimulationState.COMPLETED
        assert b"Loan amount" in response.content

    def test_slider_partial_recomputes(self, client):
        self._ready_simulation(client)
        client.get(reverse("portal:simulation_step", kwargs={"slug": "report"}))
        response = client.get(
            reverse("portal:simulation_step", kwargs={"slug": "report"}) + "?own_funds=150000&duration=25",
            headers={"hx-request": "true"},
        )
        assert response.status_code == 200
        assert b"Mortgage overview" in response.content

    def test_slider_ignores_garbage_params(self, client):
        self._ready_simulation(client)
        response = client.get(
            reverse("portal:simulation_step", kwargs={"slug": "report"}) + "?own_funds=abc&duration=xyz",
        )
        assert response.status_code == 200
