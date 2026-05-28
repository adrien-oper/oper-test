"""Uploaded documents and their AI-analysis lifecycle.

A document's status is a guarded FSM driven by the async analysis task:
``uploaded → analyzing → (analyzed | flagged | failed)``. ``flagged`` means
the AI found a mismatch against the application data; ``failed`` means the
analysis itself errored.
"""

from django.db import models
from django_fsm import FSMField, transition

from portal import enums
from portal.models.application import Application


class DocumentState(models.TextChoices):
    UPLOADED = "uploaded", "Uploaded"
    ANALYZING = "analyzing", "Analyzing"
    ANALYZED = "analyzed", "Analyzed"
    FLAGGED = "flagged", "Flagged"
    FAILED = "failed", "Analysis failed"


class Document(models.Model):
    """A supporting document linked to an application."""

    state = FSMField(default=DocumentState.UPLOADED, choices=DocumentState.choices, protected=True)

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="documents")
    kind = models.CharField(max_length=30, choices=enums.DocumentKind.choices, default=enums.DocumentKind.OTHER)
    file = models.FileField(upload_to="documents/%Y/%m/")
    original_filename = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return f"{self.original_filename or self.file.name} ({self.get_state_display()})"

    @property
    def is_terminal(self) -> bool:
        return self.state in {DocumentState.ANALYZED, DocumentState.FLAGGED, DocumentState.FAILED}

    # --- Guarded transitions ------------------------------------------------

    @transition(field=state, source=DocumentState.UPLOADED, target=DocumentState.ANALYZING)
    def start_analysis(self) -> None:
        """Mark the document as being analyzed (set by the worker task)."""

    @transition(field=state, source=DocumentState.ANALYZING, target=DocumentState.ANALYZED)
    def mark_analyzed(self) -> None:
        """Analysis completed and the document matches the application."""

    @transition(field=state, source=DocumentState.ANALYZING, target=DocumentState.FLAGGED)
    def flag(self) -> None:
        """Analysis completed but found a mismatch worth a human's attention."""

    @transition(
        field=state,
        source=[DocumentState.UPLOADED, DocumentState.ANALYZING],
        target=DocumentState.FAILED,
    )
    def fail(self) -> None:
        """Analysis could not be completed."""


class DocumentAnalysis(models.Model):
    """The structured result of analyzing a document.

    Persisted whether the AI ran live or returned the deterministic stub;
    ``is_stub`` records which path produced it so the UI can be honest.
    """

    document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name="analysis")
    detected_kind = models.CharField(max_length=30, choices=enums.DocumentKind.choices, blank=True)
    summary = models.TextField(blank=True)
    extracted_fields = models.JSONField(default=dict)
    mismatches = models.JSONField(default=list)
    is_stub = models.BooleanField(default=True)
    model_used = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        flavour = "stub" if self.is_stub else self.model_used
        return f"Analysis of {self.document_id} ({flavour})"

    @property
    def has_mismatches(self) -> bool:
        return bool(self.mismatches)
