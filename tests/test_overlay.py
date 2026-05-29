"""The teatree overlay exposes the repo to the t3 CLI correctly."""

from pathlib import Path

import pytest
from teatree.core.overlay import OverlayConfig

from overlay.overlay import BorrowerPortalMetadata, BorrowerPortalOverlay

_REPO = "adrien-oper/oper-test"


@pytest.fixture
def overlay():
    return BorrowerPortalOverlay()


class TestOverlayConfig:
    def test_has_a_config_and_metadata(self, overlay):
        assert isinstance(overlay.config, OverlayConfig)
        assert isinstance(overlay.metadata, BorrowerPortalMetadata)

    def test_targets_this_repo(self, overlay):
        assert overlay.get_repos() == [_REPO]

    def test_companion_skills_load_django_python_and_project_skill(self, overlay):
        assert overlay.config.companion_skills == ["ac-django", "ac-python", "borrower-portal"]

    def test_repo_is_declared_public_for_the_privacy_gate(self, overlay):
        assert overlay.config.public_repos == [_REPO]

    def test_review_companion_is_code_review(self, overlay):
        assert overlay.config.pr_review_companion == "code-review"

    def test_run_commands_cover_the_dev_surface(self, overlay):
        commands = overlay.get_run_commands(worktree=None)
        assert {"test", "lint", "format", "typecheck", "serve", "worker"} <= set(commands)
        assert commands["test"] == ["uv", "run", "pytest"]

    def test_test_command(self, overlay):
        assert overlay.get_test_command(worktree=None) == ["uv", "run", "pytest"]

    def test_verify_endpoints_cover_core_pages(self, overlay):
        endpoints = overlay.get_verify_endpoints(worktree=None)
        assert endpoints["home"] == "/"
        assert "dashboard" in endpoints

    def test_e2e_config_uses_playwright(self, overlay):
        assert overlay.metadata.get_e2e_config()["runner"] == "playwright"


class TestProvisionSteps:
    def test_no_worktree_path_is_a_noop(self, overlay, mocker):
        worktree = mocker.Mock(worktree_path=None)
        assert overlay.get_provision_steps(worktree) == []

    def test_worktree_path_yields_sync_then_migrate(self, overlay, mocker, tmp_path):
        worktree = mocker.Mock(worktree_path=str(tmp_path))
        steps = overlay.get_provision_steps(worktree)
        assert [step.name for step in steps] == ["sync-dependencies", "apply-migrations"]

    def test_env_extra_scopes_state_to_the_worktree_and_stubs_ai(self, overlay, mocker, tmp_path):
        worktree = mocker.Mock(worktree_path=str(tmp_path))
        env = overlay.get_env_extra(worktree)
        assert env["DOCUMENT_ANALYZER_BACKEND"] == "stub"
        assert env["SQLITE_PATH"] == str(tmp_path / "db.sqlite3")
        assert env["MEDIA_ROOT"] == str(tmp_path / "media")

    def test_env_extra_without_worktree_path_is_empty(self, overlay, mocker):
        assert overlay.get_env_extra(mocker.Mock(worktree_path=None)) == {}

    def test_cleanup_drops_local_state(self, overlay, mocker, tmp_path):
        worktree = mocker.Mock(worktree_path=str(tmp_path))
        steps = overlay.get_cleanup_steps(worktree)
        assert [step.name for step in steps] == ["drop-local-state"]
        assert steps[0].required is False

    def test_cleanup_without_worktree_path_is_a_noop(self, overlay, mocker):
        assert overlay.get_cleanup_steps(mocker.Mock(worktree_path=None)) == []


class TestPrValidation:
    @pytest.fixture
    def metadata(self):
        return BorrowerPortalMetadata()

    def test_conventional_title_passes(self, metadata):
        result = metadata.validate_pr("feat: add simulation flow", "Builds the flow")
        assert result["errors"] == []

    def test_non_conventional_type_is_rejected(self, metadata):
        result = metadata.validate_pr("add simulation flow", "desc")
        assert any("conventional-commit" in error for error in result["errors"])

    def test_missing_colon_is_rejected(self, metadata):
        result = metadata.validate_pr("feat add flow", "desc")
        assert any("<type>: <summary>" in error for error in result["errors"])

    def test_empty_description_is_rejected(self, metadata):
        result = metadata.validate_pr("feat: add flow", "   ")
        assert any("description" in error for error in result["errors"])

    def test_skill_metadata_points_at_existing_skills_dir(self, metadata):
        meta = metadata.get_skill_metadata()
        assert meta["remote_patterns"] == [_REPO]
        skill_path = Path(meta["skill_path"])
        # The overlay points at a real skills directory holding the project skill.
        assert (skill_path / "borrower-portal" / "SKILL.md").is_file()

    def test_ci_and_followup_target_the_repo(self, metadata):
        assert metadata.get_ci_project_path() == _REPO
        assert metadata.get_followup_repos() == [_REPO]

    def test_quality_tool_command_is_exposed(self, metadata):
        names = [cmd["name"] for cmd in metadata.get_tool_commands()]
        assert "quality" in names
