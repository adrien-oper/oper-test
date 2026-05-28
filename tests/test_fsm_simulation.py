"""FSM behaviour for the simulation lifecycle and conversion."""

from decimal import Decimal

import pytest
from django_fsm import TransitionNotAllowed

from portal.models import IncomeLine, Simulation, SimulationState

pytestmark = pytest.mark.django_db


def _simulation_with_income() -> Simulation:
    sim = Simulation.objects.create(property_price=Decimal(300000), own_funds=Decimal(70000))
    IncomeLine.objects.create(simulation=sim, monthly_amount=Decimal(5000))
    return sim


class TestSimulationLifecycle:
    def test_reference_is_assigned_on_create(self):
        sim = Simulation.objects.create()
        assert sim.reference.startswith("S")

    def test_complete_requires_income(self):
        sim = Simulation.objects.create(property_price=Decimal(300000))
        with pytest.raises(TransitionNotAllowed):
            sim.complete()
        assert sim.state == SimulationState.DRAFT

    def test_complete_succeeds_with_financials(self):
        sim = _simulation_with_income()
        sim.complete()
        sim.save()
        assert sim.state == SimulationState.COMPLETED

    def test_state_field_is_protected_from_manual_assignment(self):
        sim = _simulation_with_income()
        with pytest.raises(AttributeError):
            sim.state = SimulationState.COMPLETED

    def test_convert_from_completed(self):
        sim = _simulation_with_income()
        sim.complete()
        sim.save()
        sim.mark_converted()
        sim.save()
        assert sim.state == SimulationState.CONVERTED

    def test_cannot_convert_twice(self):
        sim = _simulation_with_income()
        sim.mark_converted()
        sim.save()
        with pytest.raises(TransitionNotAllowed):
            sim.mark_converted()


class TestSimulationFinancials:
    def test_totals_aggregate_lines(self):
        sim = Simulation.objects.create(property_price=Decimal(300000), own_funds=Decimal(70000))
        IncomeLine.objects.create(simulation=sim, monthly_amount=Decimal(5000))
        IncomeLine.objects.create(simulation=sim, monthly_amount=Decimal(800))
        assert sim.total_monthly_income == Decimal(5800)

    def test_feasibility_uses_stored_values(self):
        sim = _simulation_with_income()
        report = sim.feasibility()
        assert report.property_price == Decimal("300000.00")
        assert report.loan_amount > 0
