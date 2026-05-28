"""Reference data shared across the portal."""

import secrets

from django.db import models
from django.utils import timezone

_REFERENCE_RANDOM_BYTES = 3


def build_reference(prefix: str) -> str:
    """A human-readable, collision-resistant reference for a domain row.

    A timestamp keeps references roughly sortable; a short random suffix makes
    same-second collisions on the ``unique`` column vanishingly unlikely.
    """
    stamp = timezone.now().strftime("%y%m%d%H%M%S")
    return f"{prefix}{stamp}{secrets.token_hex(_REFERENCE_RANDOM_BYTES)}"


class HelpOffice(models.Model):
    """A branch / advisory office a borrower can be assigned to at sign-up."""

    name = models.CharField(max_length=120)
    city = models.CharField(max_length=120)
    address = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["city", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.city})"
