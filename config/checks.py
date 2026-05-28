"""Deploy-readiness system checks.

These run on ``manage.py check`` (and at startup) so an insecure default can
never silently ship to production.
"""

from django.conf import settings
from django.core.checks import Error, register

INSECURE_SECRET_KEY = "django-insecure-dev-only-key-change-me-in-production-0r724av6mx"  # noqa: S105


@register
def check_secret_key(**_kwargs: object) -> list[Error]:
    if not settings.DEBUG and settings.SECRET_KEY == INSECURE_SECRET_KEY:
        return [
            Error(
                "The insecure default SECRET_KEY is in use with DEBUG=False.",
                hint="Set the SECRET_KEY environment variable to a unique, secret value in production.",
                id="config.E001",
            ),
        ]
    return []
