"""Fixtures for the browser-driven end-to-end suite.

These specs drive the real app through a headless browser against Django's
``live_server``. Determinism comes from two settings pinned here for the whole
session: the document analyzer is forced to its offline ``stub`` backend and no
Anthropic key is present, so ``resolve_backend()`` never touches the network.

The async analysis task is invoked synchronously via ``run_document_analysis``
right where a real worker would pick it up — the django-tasks-db worker is not
running under ``live_server``, so the queue would otherwise never drain.
"""

import importlib
import os

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from playwright.sync_api import Page, expect

os.environ["DOCUMENT_ANALYZER_BACKEND"] = "stub"
os.environ.pop("ANTHROPIC_API_KEY", None)

# Playwright's sync API drives the browser from a thread that carries a running
# asyncio loop. pytest-django then runs the (genuinely synchronous, single-
# threaded) test-database setup and the per-test ORM calls in that same thread,
# which Django's async-safety guard refuses by default. The live server itself
# runs in its own thread, so these calls are safe; opt out of the guard here.
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "1"

User = get_user_model()

PASSWORD = "Str0ng!pass99"


def pytest_configure(config: pytest.Config) -> None:
    # The unit suite treats every warning as an error. The live-server threads
    # leave their per-thread SQLite connections to be garbage-collected, which
    # surfaces a harmless ResourceWarning at session teardown. It cannot occur
    # in the unit suite (no live_server), so silence it just for this run rather
    # than weakening the global filter.
    config.addinivalue_line("filterwarnings", "ignore::ResourceWarning")


@pytest.fixture(autouse=True)
def _stub_analyzer(settings, tmp_path):
    settings.DOCUMENT_ANALYZER_BACKEND = "stub"
    settings.ANTHROPIC_API_KEY = ""
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def live_url(live_server):
    return live_server.url


@pytest.fixture
def seeded_offices(db):
    """Apply the help-office seed migration's data function for a browser test.

    ``live_server`` drives each spec in a ``TransactionTestCase``, which flushes
    every table between tests — dropping the rows the seed migration created at
    migrate time. Re-applying the migration's own (idempotent) data function
    restores them while still exercising the real seed logic the deploy relies
    on, rather than a hand-built office.
    """
    seed = importlib.import_module("portal.migrations.0003_seed_help_offices")
    seed.seed_offices(apps, None)
    # ``live_server`` runs the test under ``transactional_db`` and serves
    # requests from its own thread. Close the connection this fixture opened on
    # the main thread so the test runner does not later touch it cross-thread.
    connection.close()


@pytest.fixture
def make_user(db):
    def _make(email="ada@example.com"):
        return User.objects.create_user(username=email, email=email, password=PASSWORD)

    return _make


@pytest.fixture
def log_in(page: Page, live_url):
    def _log_in(email="ada@example.com"):
        page.goto(f"{live_url}/login/")
        page.fill("#id_username", email)
        page.fill("#id_password", PASSWORD)
        page.click("button[type=submit]")
        expect(page).to_have_url(f"{live_url}/dashboard/")

    return _log_in
