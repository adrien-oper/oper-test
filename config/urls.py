"""Root URL configuration.

Uploaded media is intentionally NOT served via ``django.conf.urls.static`` —
that helper streams files off disk with no authentication or owner scoping,
which would expose every borrower's PII documents whenever ``DEBUG`` is on.
Documents are served only through the authenticated, owner-scoped
``portal:document_file`` view, so ownership holds in every environment.
"""

from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path

urlpatterns: list[URLPattern | URLResolver] = [
    path("admin/", admin.site.urls),
    path("", include("portal.urls")),
]
