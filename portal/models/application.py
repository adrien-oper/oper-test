"""The mortgage application and its guarded lifecycle.

An application is born by converting a completed simulation. Its status is
a real FSM: ``draft → submitted → under_review → (approved | rejected)``.
Every transition is guarded; reviewers need a permission to decide.
"""

from django.conf import settings
from django.db import models, transaction
from django_fsm import FSMField, transition

from portal import enums
from portal.models.simulation import Simulation


class ApplicationState(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    UNDER_REVIEW = "under_review", "Under review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class Application(models.Model):
    """A loan application converted from a simulation.

    The multi-step application form fills the applicant details below; the
    status is driven only through the guarded transition methods.
    """

    state = FSMField(default=ApplicationState.DRAFT, choices=ApplicationState.choices, protected=True)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications")
    simulation = models.OneToOneField(Simulation, on_delete=models.PROTECT, related_name="application")
    reference = models.CharField(max_length=20, unique=True, editable=False)

    # Applicant personal details (single multi-step form is fine per the brief).
    first_name = models.CharField(max_length=120, blank=True)
    last_name = models.CharField(max_length=120, blank=True)
    national_number = models.CharField(max_length=40, blank=True)
    current_address = models.CharField(max_length=255, blank=True)
    employment_status = models.CharField(
        max_length=20,
        choices=enums.EmploymentStatus.choices,
        default=enums.EmploymentStatus.EMPLOYEE,
    )
    employer_name = models.CharField(max_length=160, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("decide_application", "Can approve or reject an application")]

    def __str__(self) -> str:
        return f"{self.reference} — {self.get_state_display()}"

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.reference:
            self.reference = self._build_reference()
        super().save(*args, **kwargs)

    @staticmethod
    def _build_reference() -> str:
        from django.utils import timezone  # noqa: PLC0415

        stamp = timezone.now().strftime("%y%m%d%H%M%S%f")
        return f"A{stamp[:14]}"

    @classmethod
    def create_from_simulation(cls, simulation: Simulation) -> "Application":
        """Convert a simulation into an application atomically.

        Creating the application and transitioning the simulation to
        ``converted`` happen in one transaction so a half-converted state
        can never be observed.
        """
        with transaction.atomic():
            application = cls.objects.create(user=simulation.user, simulation=simulation)
            simulation.mark_converted()
            simulation.save()
        return application

    # --- Guarded transitions ------------------------------------------------

    def _personal_details_complete(self) -> bool:
        return bool(self.first_name and self.last_name and self.national_number)

    @transition(
        field=state,
        source=ApplicationState.DRAFT,
        target=ApplicationState.SUBMITTED,
        conditions=[_personal_details_complete],
    )
    def submit(self) -> None:
        """Submit the application once the applicant details are filled."""
        from django.utils import timezone  # noqa: PLC0415

        self.submitted_at = timezone.now()

    @transition(field=state, source=ApplicationState.SUBMITTED, target=ApplicationState.UNDER_REVIEW)
    def start_review(self) -> None:
        """Move a submitted application into review."""

    @transition(
        field=state,
        source=ApplicationState.UNDER_REVIEW,
        target=ApplicationState.APPROVED,
        permission="portal.decide_application",
    )
    def approve(self, *, note: str = "") -> None:
        """Approve an application under review (requires decide permission)."""
        self._record_decision(note)

    @transition(
        field=state,
        source=ApplicationState.UNDER_REVIEW,
        target=ApplicationState.REJECTED,
        permission="portal.decide_application",
    )
    def reject(self, *, note: str = "") -> None:
        """Reject an application under review (requires decide permission)."""
        self._record_decision(note)

    def _record_decision(self, note: str) -> None:
        from django.utils import timezone  # noqa: PLC0415

        self.decided_at = timezone.now()
        self.decision_note = note
