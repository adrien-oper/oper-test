"""Unit tests for the pure affordability engine (no database)."""

from decimal import Decimal

import pytest

from portal import affordability


class TestMonthlyPayment:
    def test_zero_rate_is_straight_line_repayment(self):
        payment = affordability.monthly_payment(Decimal(24000), Decimal(0), duration_years=10)
        assert payment == Decimal("200.00")

    def test_positive_rate_annuity_is_above_straight_line(self):
        principal = Decimal(200000)
        straight_line = principal / Decimal(20 * 12)
        payment = affordability.monthly_payment(principal, Decimal("3.70"), duration_years=20)
        assert payment > straight_line
        assert payment == payment.quantize(Decimal("0.01"))

    def test_zero_duration_returns_zero(self):
        assert affordability.monthly_payment(Decimal(100000), Decimal("3.0"), duration_years=0) == Decimal("0.00")


class TestRateForDuration:
    @pytest.mark.parametrize(
        ("years", "expected"),
        [(10, Decimal("3.10")), (20, Decimal("3.70")), (30, Decimal("4.30"))],
    )
    def test_known_bands(self, years, expected):
        assert affordability.annual_rate_for_duration(years) == expected

    def test_off_grid_duration_snaps_to_nearest_band(self):
        assert affordability.annual_rate_for_duration(18) == affordability.annual_rate_for_duration(20)


class TestBuildReport:
    def _report(self, **overrides):
        params = {
            "property_price": Decimal(300000),
            "own_funds": Decimal(70000),
            "monthly_income": Decimal(5800),
            "monthly_expenses": Decimal(0),
            "duration_years": 20,
        }
        params.update(overrides)
        return affordability.build_report(**params)

    def test_loan_amount_is_total_cost_minus_own_funds(self):
        report = self._report()
        expected_costs = Decimal(300000) * Decimal("0.12")
        assert report.purchase_costs == expected_costs
        assert report.total_project_cost == Decimal(300000) + expected_costs
        assert report.loan_amount == report.total_project_cost - Decimal(70000)

    def test_affordable_when_debt_ratio_under_threshold(self):
        report = self._report(monthly_income=Decimal(6000))
        assert report.within_reach is True
        assert report.debt_ratio <= affordability.MAX_DEBT_RATIO

    def test_not_affordable_on_thin_income(self):
        report = self._report(monthly_income=Decimal(1500))
        assert report.within_reach is False

    def test_own_funds_override_lowers_loan_without_touching_base(self):
        base = self._report()
        more_funds = self._report(own_funds_override=Decimal(120000))
        assert more_funds.loan_amount < base.loan_amount
        assert more_funds.own_funds == Decimal("120000.00")

    def test_duration_is_clamped_to_supported_range(self):
        report = self._report(duration_years=99)
        assert report.duration_years == affordability.MAX_DURATION_YEARS

    def test_zero_income_is_not_within_reach(self):
        report = self._report(monthly_income=Decimal(0))
        assert report.within_reach is False
        assert report.net_disposable_income == Decimal("0.00")

    def test_own_funds_cover_everything_means_no_loan(self):
        report = self._report(own_funds=Decimal(400000))
        assert report.loan_amount == Decimal("0.00")
        assert report.monthly_payment == Decimal("0.00")
