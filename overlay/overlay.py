"""The borrower-portal overlay class.

Implements only the two abstract OverlayBase hooks (``get_repos`` and
``get_provision_steps``) plus a handful of convenience overrides that make
``t3`` run the right commands and enforce a conventional-commit PR title.
Everything else inherits teatree's defaults.
"""

from pathlib import Path
from typing import TYPE_CHECKING, override

from teatree.core.overlay import OverlayBase, OverlayConfig, OverlayMetadata
from teatree.types import ProvisionStep, RunCommands, SkillMetadata, ValidationResult
from teatree.utils.run import run_checked

if TYPE_CHECKING:
    # Imported for typing only — referencing it at runtime would boot teatree's
    # Django app, which this lightweight overlay must not require.
    from teatree.core.models import Worktree

_CONVENTIONAL_PREFIXES = ("feat", "fix", "docs", "refactor", "test", "chore", "perf", "build", "ci")


def _repo_root() -> Path:
    """Directory that holds this repo's ``pyproject.toml``."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    msg = f"Cannot find repo root from {here}"
    raise FileNotFoundError(msg)


class BorrowerPortalMetadata(OverlayMetadata):
    """PR conventions and skill discovery for the portal repo."""

    @override
    def validate_pr(self, title: str, description: str) -> ValidationResult:
        errors: list[str] = []
        if not any(title.startswith(f"{prefix}") for prefix in _CONVENTIONAL_PREFIXES):
            allowed = ", ".join(_CONVENTIONAL_PREFIXES)
            errors.append(f"PR title must start with a conventional-commit type ({allowed}).")
        if ":" not in title:
            errors.append("PR title must be of the form '<type>: <summary>'.")
        if not description.strip():
            errors.append("PR description must not be empty.")
        return {"errors": errors, "warnings": []}

    @override
    def get_skill_metadata(self) -> SkillMetadata:
        return {
            "skill_path": str(_repo_root() / ".claude" / "skills"),
            "remote_patterns": ["adrien-oper/oper-test"],
        }


class BorrowerPortalOverlay(OverlayBase):
    """Lightweight teatree overlay targeting the borrower-portal repo."""

    config = OverlayConfig(overlay_name="borrower-portal")
    metadata = BorrowerPortalMetadata()

    @override
    def get_repos(self) -> list[str]:
        return ["adrien-oper/oper-test"]

    @override
    def get_provision_steps(self, worktree: "Worktree") -> list[ProvisionStep]:
        on_disk = worktree.worktree_path
        if not on_disk:
            return []
        repo = Path(on_disk)

        def sync_deps() -> None:
            run_checked(["uv", "sync"], cwd=repo)

        return [
            ProvisionStep(
                name="sync-dependencies",
                callable=sync_deps,
                description="Install Python dependencies with uv sync",
            ),
        ]

    @override
    def get_run_commands(self, worktree: "Worktree") -> RunCommands:
        return {
            "test": ["uv", "run", "pytest"],
            "lint": ["uv", "run", "ruff", "check", "."],
            "serve": ["uv", "run", "python", "manage.py", "runserver"],
        }

    @override
    def get_test_command(self, worktree: "Worktree") -> list[str]:
        return ["uv", "run", "pytest"]
