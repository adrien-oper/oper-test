"""The mortgage application and its guarded lifecycle.

An application is born by converting a completed simulation. Its status is
a real FSM: ``draft → submitted → under_review → (approved | rejected)``.
Every transition is guarded; reviewers need a permission to decide.
"""

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone
from django_fsm import FSMField, has_transition_perm, transition

from portal import enums
from portal.models.reference import build_reference
from portal.models.simulation import Simulation, SimulationState


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
        return build_reference("A")

    @classmethod
    def create_from_simulation(cls, simulation: Simulation) -> "Application":
        """Convert a simulation into an application atomically.

        Creating the application and transitioning the simulation to
        ``converted`` happen in one transaction so a half-converted state
        can never be observed. Only a ``completed`` simulation may be
        converted, so the financial-completeness guard is never bypassed.
        """
        if simulation.state != SimulationState.COMPLETED:
            msg = "Only a completed simulation can be converted to an application."
            raise ValidationError(msg)
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
        self.submitted_at = timezone.now()

    @transition(field=state, source=ApplicationState.SUBMITTED, target=ApplicationState.UNDER_REVIEW)
    def start_review(self) -> None:
        """Move a submitted application into review."""

    def submit_for_review(self) -> None:
        """Submit then open review as one atomic step.

        Mirrors :meth:`create_from_simulation`: the two guarded transitions and
        their saves happen in one transaction, so a submitted-but-not-reviewed
        row can never be observed if either save fails.
        """
        with transaction.atomic():
            self.submit()
            self.save()
            self.start_review()
            self.save()

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

    def decide(self, actor: settings.AUTH_USER_MODEL, *, approve: bool, note: str = "") -> None:
        """Approve or reject under review, enforcing the actor's permission.

        The ``permission=`` on the transitions is only metadata; this is the
        single entry point that checks it against a real actor before running
        the guarded transition and persisting.
        """
        decision = self.approve if approve else self.reject
        if not has_transition_perm(decision, actor):
            msg = "You do not have permission to decide on this application."
            raise PermissionDenied(msg)
        with transaction.atomic():
            decision(note=note)
            self.save()

    def _record_decision(self, note: str) -> None:
        self.decided_at = timezone.now()
        self.decision_note = note
