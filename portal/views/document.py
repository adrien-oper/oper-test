"""Document upload and analysis status.

Uploading a document creates it in the ``uploaded`` state and enqueues the
analysis task *after the surrounding transaction commits*, so the worker
never races a not-yet-persisted row. The detail view shows the document's
FSM state and, once available, the AI analysis (stub or live).
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from portal.forms import DocumentUploadForm
from portal.models import Application, ApplicationState, Document
from portal.tasks import analyze_document_task
from portal.views._shared import get_owned_or_404

_DECIDED_STATES = {ApplicationState.APPROVED, ApplicationState.REJECTED}


@login_required
def upload_document(request: HttpRequest, pk: int) -> HttpResponse:
    """Upload a supporting document linked to an application and analyze it.

    Refused once the application is decided: a reviewer should not have new
    documents (and fresh AI analysis) attached to an application they have
    already approved or rejected.
    """
    application = get_owned_or_404(request, Application, pk)
    if application.state in _DECIDED_STATES:
        messages.error(request, "This application has been decided; you can no longer add documents.")
        return redirect("portal:application_detail", pk=application.pk)
    if request.method == "POST":
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.application = application
            document.original_filename = document.file.name
            document.save()
            transaction.on_commit(lambda: analyze_document_task.enqueue(document.pk))
            return redirect("portal:document_detail", pk=document.pk)
    else:
        form = DocumentUploadForm()
    return render(
        request,
        "portal/document/upload.html",
        {"form": form, "application": application},
    )


@login_required
def document_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Show a document's analysis status and result.

    Polled by HTMX every two seconds while the document is non-terminal; the
    poll swaps the status partial, whose trigger attributes drop once the
    document reaches a terminal state, so the polling cancels itself.
    """
    document = get_object_or_404(Document.objects.for_owner(request.user), pk=pk)
    context = {"document": document, "analysis": getattr(document, "analysis", None)}
    if request.headers.get("HX-Request"):
        return render(request, "portal/document/_status.html", context)
    return render(request, "portal/document/detail.html", context)


@login_required
def document_file(request: HttpRequest, pk: int) -> FileResponse:
    """Stream an uploaded document file, scoped to its owner.

    Uploaded files carry PII (ID cards, payslips, bank statements). They are
    served only through this authenticated, owner-scoped view — never through
    a public static-media route — so ownership holds in every environment, not
    just behind ``DEBUG``.
    """
    document = get_object_or_404(Document.objects.for_owner(request.user), pk=pk)
    return FileResponse(document.file.open("rb"), filename=document.original_filename or document.file.name)
