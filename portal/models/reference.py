"""Reference data shared across the portal."""

import secrets

from django.conf import settings
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


class BorrowerProfile(models.Model):
    """Persistent onboarding state for a signed-up borrower.

    The sign-up flow used to keep the chosen help office and the phone
    verification flag in the session, so they were lost on logout. This
    one-to-one row makes those choices durable.
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="borrower_profile")
    help_office = models.ForeignKey(
        HelpOffice, null=True, blank=True, on_delete=models.SET_NULL, related_name="borrowers"
    )
    phone_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Profile of {self.user} (verified={self.phone_verified})"

    @property
    def onboarding_complete(self) -> bool:
        return self.phone_verified and self.help_office_id is not None
