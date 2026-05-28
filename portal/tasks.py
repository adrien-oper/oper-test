"""Async work — document analysis driven by django-tasks.

The task reads the uploaded file, runs the analyzer, persists the result, and
drives the document's FSM to its terminal state. It is idempotent: a document
already past ``uploaded`` is skipped, so a retry can never double-transition.
"""

from django_tasks import task

from portal.ai.analyzer import ApplicationFacts, analyze_document
from portal.models import Document, DocumentAnalysis, DocumentState

_MAX_TEXT_BYTES = 200_000


def _read_text(document: Document) -> str:
    """Best-effort decode of the uploaded file's first chunk as text."""
    try:
        with document.file.open("rb") as handle:
            raw = handle.read(_MAX_TEXT_BYTES)
    except (OSError, ValueError):
        return ""
    return raw.decode("utf-8", errors="replace")


def _facts_for(document: Document) -> ApplicationFacts:
    application = document.application
    full_name = f"{application.first_name} {application.last_name}".strip()
    return ApplicationFacts(
        full_name=full_name,
        national_number=application.national_number,
        property_price=application.simulation.property_price,
    )


def run_document_analysis(document_id: int) -> None:
    """Analyze one document and transition its FSM to a terminal state.

    Extracted from the task body so it can be called synchronously in tests
    and in environments without a running worker.
    """
    document = Document.objects.filter(pk=document_id).first()
    if document is None or document.state != DocumentState.UPLOADED:
        return

    document.start_analysis()
    document.save()

    try:
        result = analyze_document(_read_text(document), document.original_filename, _facts_for(document))
    except Exception:  # noqa: BLE001 — any analyzer failure must fail the FSM, not crash the worker
        document.fail()
        document.save()
        return

    DocumentAnalysis.objects.update_or_create(
        document=document,
        defaults={
            "detected_kind": result.detected_kind,
            "summary": result.summary,
            "extracted_fields": result.extracted_fields,
            "mismatches": result.mismatches,
            "is_stub": result.is_stub,
            "model_used": result.model_used,
        },
    )

    if result.mismatches:
        document.flag()
    else:
        document.mark_analyzed()
    document.save()


@task()
def analyze_document_task(document_id: int) -> None:
    """django-tasks entry point for document analysis."""
    run_document_analysis(document_id)
