"""The borrower-portal overlay class.

A teatree overlay that teaches the open-source ``t3`` CLI how to develop,
provision, run, test, and review this repo. It composes ``OverlayConfig`` and
``OverlayMetadata`` per teatree's overlay conventions and implements the
relevant ``OverlayBase`` extension hooks. It deliberately does NOT bundle
multi-tenant DB orchestration, loop slots, or messaging backends — this is a
single-repo SQLite project, so those defaults stay untouched. teatree is a
dev-only dependency and is never imported by the Django app at runtime.
"""

from pathlib import Path
from typing import TYPE_CHECKING, override

from teatree.core.overlay import OverlayBase, OverlayConfig, OverlayMetadata
from teatree.types import ProvisionStep, RunCommands, SkillMetadata, ToolCommand, ValidationResult
from teatree.utils.run import run_checked

if TYPE_CHECKING:
    # Imported for typing only — referencing it at runtime would boot teatree's
    # Django app, which this lightweight overlay must not require.
    from teatree.core.models import Worktree

_REPO = "adrien-oper/oper-test"
_CONVENTIONAL_PREFIXES = ("feat", "fix", "docs", "refactor", "test", "chore", "perf", "build", "ci")


def _repo_root() -> Path:
    """Directory that holds this repo's ``pyproject.toml``."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    msg = f"Cannot find repo root from {here}"
    raise FileNotFoundError(msg)


def _build_config() -> OverlayConfig:
    """Compose the overlay's static configuration.

    Wires the standing companion skills (so ``ac-django``/``ac-python`` and the
    project skill load alongside whichever lifecycle skill is active), declares
    the repo public so teatree's pre-publish privacy gate runs, and points
    review at the bundled ``code-review`` companion.
    """
    config = OverlayConfig(overlay_name="borrower-portal")
    config.code_host = "github"
    config.github_owner = "adrien-oper"
    config.companion_skills = ["ac-django", "ac-python", "borrower-portal"]
    config.public_repos = [_REPO]
    config.protected_branches = ["main"]
    config.pr_review_companion = "code-review"
    return config


class BorrowerPortalMetadata(OverlayMetadata):
    """PR conventions, CI path, and skill discovery for the portal repo."""

    @override
    def validate_pr(self, title: str, description: str) -> ValidationResult:
        errors: list[str] = []
        if not any(title.startswith(prefix) for prefix in _CONVENTIONAL_PREFIXES):
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
            "remote_patterns": [_REPO],
        }

    @override
    def get_ci_project_path(self) -> str:
        return _REPO

    @override
    def get_followup_repos(self) -> list[str]:
        return [_REPO]

    @override
    def get_e2e_config(self) -> dict[str, str]:
        return {"runner": "playwright", "command": "uv run --group e2e pytest e2e --no-cov"}

    @override
    def get_tool_commands(self) -> list[ToolCommand]:
        return [
            {
                "name": "quality",
                "help": "Run the full quality gate: ruff check, ruff format --check, ty, pytest.",
                "command": (
                    "uv run ruff check . && uv run ruff format --check . "
                    "&& uv run ty check portal config && uv run pytest"
                ),
            },
        ]


class BorrowerPortalOverlay(OverlayBase):
    """Teatree overlay targeting the borrower-portal repo."""

    config = _build_config()
    metadata = BorrowerPortalMetadata()

    @override
    def get_repos(self) -> list[str]:
        return [_REPO]

    @override
    def get_provision_steps(self, worktree: "Worktree") -> list[ProvisionStep]:
        on_disk = worktree.worktree_path
        if not on_disk:
            return []
        repo = Path(on_disk)

        def sync_deps() -> None:
            run_checked(["uv", "sync"], cwd=repo)

        def migrate() -> None:
            run_checked(["uv", "run", "python", "manage.py", "migrate", "--noinput"], cwd=repo)

        return [
            ProvisionStep(
                name="sync-dependencies",
                callable=sync_deps,
                description="Install Python dependencies with uv sync",
            ),
            ProvisionStep(
                name="apply-migrations",
                callable=migrate,
                description="Apply database migrations against the worktree SQLite file",
            ),
        ]

    @override
    def get_env_extra(self, worktree: "Worktree") -> dict[str, str]:
        # Keep the worktree's SQLite file and uploaded media inside the
        # worktree, and run the analyzer in the free offline stub by default —
        # the live SDK path turns on only when the developer exports a key.
        on_disk = worktree.worktree_path
        if not on_disk:
            return {}
        repo = Path(on_disk)
        return {
            "SQLITE_PATH": str(repo / "db.sqlite3"),
            "MEDIA_ROOT": str(repo / "media"),
            "DOCUMENT_ANALYZER_BACKEND": "stub",
        }

    @override
    def get_run_commands(self, worktree: "Worktree") -> RunCommands:
        return {
            "test": ["uv", "run", "pytest"],
            "lint": ["uv", "run", "ruff", "check", "."],
            "format": ["uv", "run", "ruff", "format", "."],
            "typecheck": ["uv", "run", "ty", "check", "portal", "config"],
            "serve": ["uv", "run", "python", "manage.py", "runserver"],
            "worker": ["uv", "run", "python", "manage.py", "db_worker"],
        }

    @override
    def get_test_command(self, worktree: "Worktree") -> list[str]:
        return ["uv", "run", "pytest"]

    @override
    def get_verify_endpoints(self, worktree: "Worktree") -> dict[str, str]:
        return {"home": "/", "dashboard": "/dashboard/", "admin": "/admin/login/"}

    @override
    def get_cleanup_steps(self, worktree: "Worktree") -> list[ProvisionStep]:
        on_disk = worktree.worktree_path
        if not on_disk:
            return []
        repo = Path(on_disk)

        def drop_local_state() -> None:
            for leftover in (repo / "db.sqlite3", repo / "media"):
                run_checked(["rm", "-rf", str(leftover)], cwd=repo)

        return [
            ProvisionStep(
                name="drop-local-state",
                callable=drop_local_state,
                required=False,
                description="Remove the worktree SQLite file and uploaded media",
            ),
        ]
