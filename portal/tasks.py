"""Async work — document analysis driven by django-tasks.

The task reads the uploaded file, runs the analyzer, persists the result, and
drives the document's FSM to its terminal state.

It is **resumable**: a document is claimed from either ``uploaded`` or a
stranded ``analyzing`` state (a crash mid-flight no longer wedges it), and the
claim runs under a row lock so two workers cannot both drive it. Failures are
split: output the analyzer judges invalid, or an unsupported file type, is a
*terminal* ``failed``; transient errors (I/O, network) propagate so the task
backend can retry, leaving the document resumable in ``analyzing``.
"""

from django.db import transaction
from django_tasks import task

from portal.ai.analyzer import AnalysisResult, ApplicationFacts, InvalidAnalysisError, analyze_document
from portal.ai.extraction import UnsupportedDocumentError, extract_text
from portal.models import Document, DocumentAnalysis, DocumentState

_RESUMABLE_STATES = {DocumentState.UPLOADED, DocumentState.ANALYZING}
_TERMINAL_ANALYSIS_ERRORS = (InvalidAnalysisError, UnsupportedDocumentError)


def _claim(document_id: int) -> Document | None:
    """Lock the row and move it into ``analyzing``; return None if not claimable."""
    with transaction.atomic():
        document = Document.objects.select_for_update().filter(pk=document_id).first()
        if document is None or document.state not in _RESUMABLE_STATES:
            return None
        if document.state == DocumentState.UPLOADED:
            document.start_analysis()
            document.save()
        return document


def _read_text(document: Document) -> str:
    with document.file.open("rb") as handle:
        raw = handle.read()
    return extract_text(document.original_filename or document.file.name, raw)


def _facts_for(document: Document) -> ApplicationFacts:
    application = document.application
    return ApplicationFacts(
        full_name=f"{application.first_name} {application.last_name}".strip(),
        national_number=application.national_number,
        property_price=application.simulation.property_price,
    )


def _finalize(document_id: int, result: AnalysisResult) -> None:
    with transaction.atomic():
        document = Document.objects.select_for_update().filter(pk=document_id).first()
        if document is None or document.state != DocumentState.ANALYZING:
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


def _fail(document_id: int) -> None:
    with transaction.atomic():
        document = Document.objects.select_for_update().filter(pk=document_id).first()
        if document is not None and document.state == DocumentState.ANALYZING:
            document.fail()
            document.save()


def run_document_analysis(document_id: int) -> None:
    """Analyze one document and transition its FSM to a terminal state.

    Extracted from the task body so it can be called synchronously in tests
    and in environments without a running worker.
    """
    document = _claim(document_id)
    if document is None:
        return

    try:
        result = analyze_document(_read_text(document), document.original_filename, _facts_for(document))
    except _TERMINAL_ANALYSIS_ERRORS:
        _fail(document_id)
        return

    _finalize(document_id, result)


@task()
def analyze_document_task(document_id: int) -> None:
    """django-tasks entry point for document analysis."""
    run_document_analysis(document_id)
