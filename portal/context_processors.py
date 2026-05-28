"""Template context processors."""

from django.http import HttpRequest


def brand(request: HttpRequest) -> dict[str, str]:  # noqa: ARG001
    """Expose white-label brand strings to every template."""
    return {"brand_name": "Demo Bank"}
