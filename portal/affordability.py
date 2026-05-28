"""Mortgage affordability engine — pure functions, no database.

A deliberately simplified model of a Belgian-style mortgage feasibility
calculation. It is good enough to drive a believable simulation report and
the affordability sliders, and it is fully unit-testable in isolation.

Nothing here is financial advice; the numbers are illustrative.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

# Indicative annual rate by duration band. A real lender would price on a
# grid of risk factors; one rate per duration is plenty for a simulation.
_RATE_BY_DURATION_YEARS = {
    10: Decimal("3.10"),
    15: Decimal("3.40"),
    20: Decimal("3.70"),
    25: Decimal("3.95"),
    30: Decimal("4.30"),
}
DEFAULT_DURATION_YEARS = 20
MIN_DURATION_YEARS = 10
MAX_DURATION_YEARS = 30

# Share of net disposable income a lender will let go to mortgage payments.
MAX_DEBT_RATIO = Decimal("0.40")

_CENTS = Decimal("0.01")
_MONTHS_PER_YEAR = 12


def annual_rate_for_duration(duration_years: int) -> Decimal:
    """Indicative annual interest rate (percent) for a loan duration."""
    nearest = min(_RATE_BY_DURATION_YEARS, key=lambda y: abs(y - duration_years))
    return _RATE_BY_DURATION_YEARS[nearest]


def monthly_payment(principal: Decimal, annual_rate_pct: Decimal, duration_years: int) -> Decimal:
    """Fixed-rate annuity payment for a loan, rounded to cents.

    Falls back to straight-line repayment when the rate is zero.
    """
    months = duration_years * _MONTHS_PER_YEAR
    if months <= 0:
        return Decimal("0.00")
    monthly_rate = annual_rate_pct / Decimal(100) / Decimal(_MONTHS_PER_YEAR)
    if monthly_rate == 0:
        return (principal / Decimal(months)).quantize(_CENTS, rounding=ROUND_HALF_UP)
    factor = (Decimal(1) + monthly_rate) ** months
    payment = principal * monthly_rate * factor / (factor - Decimal(1))
    return payment.quantize(_CENTS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class FeasibilityReport:
    """The headline numbers shown on the simulation report."""

    loan_amount: Decimal
    own_funds: Decimal
    property_price: Decimal
    purchase_costs: Decimal
    total_project_cost: Decimal
    duration_years: int
    annual_rate_pct: Decimal
    monthly_payment: Decimal
    total_to_reimburse: Decimal
    net_disposable_income: Decimal
    debt_ratio: Decimal
    within_reach: bool


def purchase_costs(property_price: Decimal, *, registration_rate: Decimal = Decimal("0.12")) -> Decimal:
    """Indicative purchase costs (registration duties, notary, fees)."""
    return (property_price * registration_rate).quantize(_CENTS, rounding=ROUND_HALF_UP)


def build_report(
    *,
    property_price: Decimal,
    own_funds: Decimal,
    monthly_income: Decimal,
    monthly_expenses: Decimal,
    duration_years: int = DEFAULT_DURATION_YEARS,
    own_funds_override: Decimal | None = None,
) -> FeasibilityReport:
    """Compute a feasibility report for a property purchase.

    ``own_funds_override`` lets the affordability slider re-run the maths
    with a different down-payment without mutating the stored simulation.
    """
    duration_years = max(MIN_DURATION_YEARS, min(MAX_DURATION_YEARS, duration_years))
    funds = own_funds if own_funds_override is None else own_funds_override
    funds = max(Decimal(0), funds)

    costs = purchase_costs(property_price)
    total_project_cost = property_price + costs
    loan_amount = max(Decimal(0), total_project_cost - funds)

    rate = annual_rate_for_duration(duration_years)
    payment = monthly_payment(loan_amount, rate, duration_years)
    total_to_reimburse = (payment * Decimal(duration_years * _MONTHS_PER_YEAR)).quantize(
        _CENTS,
        rounding=ROUND_HALF_UP,
    )

    net_disposable = max(Decimal(0), monthly_income - monthly_expenses)
    debt_ratio = (payment / net_disposable).quantize(Decimal("0.001")) if net_disposable > 0 else Decimal(99)
    within_reach = debt_ratio <= MAX_DEBT_RATIO

    return FeasibilityReport(
        loan_amount=loan_amount.quantize(_CENTS, rounding=ROUND_HALF_UP),
        own_funds=funds.quantize(_CENTS, rounding=ROUND_HALF_UP),
        property_price=property_price.quantize(_CENTS, rounding=ROUND_HALF_UP),
        purchase_costs=costs,
        total_project_cost=total_project_cost.quantize(_CENTS, rounding=ROUND_HALF_UP),
        duration_years=duration_years,
        annual_rate_pct=rate,
        monthly_payment=payment,
        total_to_reimburse=total_to_reimburse,
        net_disposable_income=net_disposable.quantize(_CENTS, rounding=ROUND_HALF_UP),
        debt_ratio=debt_ratio,
        within_reach=within_reach,
    )
