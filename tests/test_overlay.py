"""The lightweight teatree overlay exposes the repo to the t3 CLI correctly."""

import pytest
from teatree.core.overlay import OverlayConfig

from overlay.overlay import BorrowerPortalMetadata, BorrowerPortalOverlay


@pytest.fixture
def overlay():
    return BorrowerPortalOverlay()


class TestOverlayConfig:
    def test_has_a_config_and_metadata(self, overlay):
        assert isinstance(overlay.config, OverlayConfig)
        assert isinstance(overlay.metadata, BorrowerPortalMetadata)

    def test_targets_this_repo(self, overlay):
        assert overlay.get_repos() == ["adrien-oper/oper-test"]

    def test_run_commands_cover_test_lint_serve(self, overlay):
        commands = overlay.get_run_commands(worktree=None)
        assert set(commands) == {"test", "lint", "serve"}
        assert commands["test"] == ["uv", "run", "pytest"]

    def test_test_command(self, overlay):
        assert overlay.get_test_command(worktree=None) == ["uv", "run", "pytest"]


class TestProvisionSteps:
    def test_no_worktree_path_is_a_noop(self, overlay, mocker):
        worktree = mocker.Mock(worktree_path=None)
        assert overlay.get_provision_steps(worktree) == []

    def test_worktree_path_yields_sync_step(self, overlay, mocker, tmp_path):
        worktree = mocker.Mock(worktree_path=str(tmp_path))
        steps = overlay.get_provision_steps(worktree)
        assert [step.name for step in steps] == ["sync-dependencies"]


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

    def test_skill_metadata_points_at_repo(self, metadata):
        meta = metadata.get_skill_metadata()
        assert meta["remote_patterns"] == ["adrien-oper/oper-test"]
