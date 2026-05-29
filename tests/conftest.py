"""Shared pytest fixtures for the borrower portal test suite."""

import pytest
from django.test import override_settings


@pytest.fixture(autouse=True)
def _isolate_media_root(tmp_path):
    """Write every uploaded file under a per-test tmp dir, never the repo.

    Without this, document-upload tests persist real files into the project's
    MEDIA_ROOT and litter the working tree.
    """
    with override_settings(MEDIA_ROOT=tmp_path):
        yield
