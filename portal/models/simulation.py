"""The anonymous simulation and its guarded lifecycle.

A simulation can be created and completed without an account. When the
visitor signs up it is claimed (linked to the user). Choosing to apply
converts it into an :class:`~portal.models.application.Application` — a
guarded FSM transition, never a manual status write.
"""

from decimal import Decimal
from functools import cached_property

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django_fsm import FSMField, transition

from portal import affordability, enums
from portal.models.reference import build_reference


class SimulationState(models.TextChoices):
    DRAFT = "draft", "Draft"
    COMPLETED = "completed", "Completed"
    CONVERTED = "converted", "Converted to application"


class SimulationQuerySet(models.QuerySet):
    def for_dashboard(self) -> "SimulationQuerySet":
        """Shape rows for the dashboard list.

        Feasibility reads income/expense lines per row, so prefetch them to keep
        the page query count flat. A converted row links to its application, so
        pull that one-to-one in the same go rather than per row.
        """
        return self.prefetch_related("incomes", "expenses", "application")


class Simulation(models.Model):
    """A mortgage feasibility simulation.

    Lifecycle: ``draft`` (being filled, may be anonymous) → ``completed``
    (feasibility report computed) → ``converted`` (an application was
    created from it). All transitions go through guarded FSM methods.
    """

    state = FSMField(default=SimulationState.DRAFT, choices=SimulationState.choices, protected=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="simulations",
    )
    reference = models.CharField(max_length=20, unique=True, editable=False)

    purpose = models.CharField(max_length=20, choices=enums.ProjectPurpose.choices, default=enums.ProjectPurpose.BUY)
    borrower_count = models.IntegerField(
        choices=enums.BorrowerCount.choices,
        default=enums.BorrowerCount.ALONE,
    )

    property_type = models.CharField(
        max_length=20, choices=enums.PropertyType.choices, default=enums.PropertyType.HOUSE
    )
    region = models.CharField(max_length=20, choices=enums.Region.choices, default=enums.Region.FLANDERS)
    property_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("300000.00"))
    property_usage = models.CharField(
        max_length=20,
        choices=enums.PropertyUsage.choices,
        default=enums.PropertyUsage.OWN_HOME,
    )

    own_funds = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    duration_years = models.IntegerField(default=affordability.DEFAULT_DURATION_YEARS)

    date_of_birth = models.DateField(null=True, blank=True)
    dependents = models.IntegerField(default=0, validators=[MinValueValidator(0)])

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SimulationQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.reference} — {self.property_price} ({self.get_state_display()})"

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.reference:
            self.reference = self._build_reference()
        super().save(*args, **kwargs)

    @staticmethod
    def _build_reference() -> str:
        return build_reference("S")

    # --- Derived financials -------------------------------------------------

    @cached_property
    def total_monthly_income(self) -> Decimal:
        return sum((line.monthly_amount for line in self.incomes.all()), Decimal("0.00"))

    @cached_property
    def total_monthly_expenses(self) -> Decimal:
        return sum((line.monthly_amount for line in self.expenses.all()), Decimal("0.00"))

    def feasibility(
        self, *, own_funds_override: Decimal | None = None, duration_years: int | None = None
    ) -> affordability.FeasibilityReport:
        """Compute the feasibility report, optionally with slider overrides."""
        return affordability.build_report(
            property_price=self.property_price,
            own_funds=self.own_funds,
            monthly_income=self.total_monthly_income,
            monthly_expenses=self.total_monthly_expenses,
            duration_years=duration_years or self.duration_years,
            own_funds_override=own_funds_override,
        )

    # --- Guarded transitions ------------------------------------------------

    def _has_financials(self) -> bool:
        return self.property_price > 0 and self.incomes.exists()

    @transition(
        field=state,
        source=SimulationState.DRAFT,
        target=SimulationState.COMPLETED,
        conditions=[_has_financials],
    )
    def complete(self) -> None:
        """Mark the simulation finished and ready to view as a report."""

    @transition(
        field=state,
        source=SimulationState.COMPLETED,
        target=SimulationState.CONVERTED,
    )
    def mark_converted(self) -> None:
        """Record that an application was created from this simulation.

        Called by :meth:`Application.create_from_simulation`; the application
        creation and this transition are wrapped in one DB transaction.
        """


class IncomeLine(models.Model):
    """A single income row attached to a simulation (add-row UI)."""

    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name="incomes")
    income_type = models.CharField(max_length=20, choices=enums.IncomeType.choices, default=enums.IncomeType.SALARY)
    monthly_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    borrower_index = models.IntegerField(default=1)

    class Meta:
        ordering = ["pk"]

    def __str__(self) -> str:
        return f"{self.get_income_type_display()}: {self.monthly_amount}"


class ExpenseLine(models.Model):
    """A single recurring expense row attached to a simulation."""

    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name="expenses")
    expense_type = models.CharField(max_length=20, choices=enums.ExpenseType.choices, default=enums.ExpenseType.OTHER)
    monthly_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        ordering = ["pk"]

    def __str__(self) -> str:
        return f"{self.get_expense_type_display()}: {self.monthly_amount}"
