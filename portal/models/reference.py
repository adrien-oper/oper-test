"""Reference data shared across the portal."""

from django.db import models


class HelpOffice(models.Model):
    """A branch / advisory office a borrower can be assigned to at sign-up."""

    name = models.CharField(max_length=120)
    city = models.CharField(max_length=120)
    address = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["city", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.city})"
