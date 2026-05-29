"""Shared helpers for the portal views."""

from django.db.models import Model, QuerySet
from django.http import HttpRequest
from django.shortcuts import get_object_or_404


def get_owned_or_404[M: Model](
    request: HttpRequest, source: type[M] | QuerySet[M], pk: int, *, owner_path: str = "user"
) -> M:
    """Fetch a row by ``pk`` that belongs to the requesting user, or 404.

    Centralises the ``get_object_or_404(Model, pk=pk, user=request.user)``
    pattern repeated across the apply, document and recap views, so ownership
    scoping is expressed once and cannot drift. ``owner_path`` names the lookup
    from the row to its owning user (e.g. ``application__user`` for documents).
    """
    return get_object_or_404(source, pk=pk, **{owner_path: request.user})
