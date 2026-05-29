"""Document upload and analysis status.

Uploading a document creates it in the ``uploaded`` state and enqueues the
analysis task *after the surrounding transaction commits*, so the worker
never races a not-yet-persisted row. The detail view shows the document's
FSM state and, once available, the AI analysis (stub or live).
"""

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from portal.forms import DocumentUploadForm
from portal.models import Application, Document
from portal.tasks import analyze_document_task
from portal.views._shared import get_owned_or_404


@login_required
def upload_document(request: HttpRequest, pk: int) -> HttpResponse:
    """Upload a supporting document linked to an application and analyze it."""
    application = get_owned_or_404(request, Application, pk)
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
    """Show a document's analysis status and result."""
    document = get_object_or_404(Document.objects.for_owner(request.user), pk=pk)
    analysis = getattr(document, "analysis", None)
    return render(
        request,
        "portal/document/detail.html",
        {"document": document, "analysis": analysis},
    )
