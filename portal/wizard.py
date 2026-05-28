"""The simulation wizard step sequence — the single source of truth.

Both the sidebar progress tracker and the next/back navigation read from
this ordering, so adding or reordering a step happens in exactly one place.
"""

from dataclasses import dataclass

SIMULATION_SESSION_KEY = "simulation_id"


@dataclass(frozen=True)
class Step:
    slug: str
    label: str
    group: str


SIMULATION_STEPS: tuple[Step, ...] = (
    Step("purpose", "Project purpose", "About project"),
    Step("borrowers", "Borrowers", "About project"),
    Step("project", "Project details", "About project"),
    Step("contribution", "Your contribution", "About project"),
    Step("income", "Your income", "Financial details"),
    Step("expenses", "Your expenses", "Financial details"),
    Step("personal", "Personal details", "Personal details"),
    Step("report", "Simulation report", "Simulation report"),
)

_SLUGS = [step.slug for step in SIMULATION_STEPS]


def next_slug(slug: str) -> str | None:
    """The slug after ``slug``, or None if it is the last step."""
    idx = _SLUGS.index(slug)
    return _SLUGS[idx + 1] if idx + 1 < len(_SLUGS) else None


def previous_slug(slug: str) -> str | None:
    """The slug before ``slug``, or None if it is the first step."""
    idx = _SLUGS.index(slug)
    return _SLUGS[idx - 1] if idx > 0 else None


def step_index(slug: str) -> int:
    """Zero-based position of ``slug`` in the sequence."""
    return _SLUGS.index(slug)
