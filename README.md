# Borrower Portal

A minimal white-label mortgage borrower portal with AI document analysis.
Server-rendered Django 6 + HTMX, no SPA, single-repo monolith.

> Work in progress. The domain core (guarded state machines + affordability
> engine) and project scaffold are in place; the HTMX flow, AI analysis task,
> and deployment are being built on top.

## What it does (target flow)

1. **Simulate** (anonymous) — purpose, borrowers, project, contribution,
   income, expenses → a feasibility report with affordability sliders.
2. **Sign up** — email + password, phone verification (stub), pick a help office.
3. **Dashboard** — saved simulations; start a new one or apply on one.
4. **Apply** — recap the simulation, convert it to an application, fill a
   multi-step form, submit; the dashboard shows status.
5. **Documents** — upload a supporting document; an async task runs AI
   classification + field extraction + mismatch detection against the
   application data.

## Architecture

- **Django 6 + HTMX**, server-rendered templates, SQLite.
- **Guarded state machines** (`django-fsm-2`) model every lifecycle — no status
  is ever written by hand:
  - `Simulation`: `draft → completed → converted`
  - `Application`: `draft → submitted → under_review → approved | rejected`
  - `Document`: `uploaded → analyzing → analyzed | flagged | failed`
  - Simulation → application is itself a guarded, atomic transition.
- **Fat models**: business logic (affordability maths, transitions, conversion)
  lives on models and a pure `affordability` engine, not in views. QuerySet
  methods (`Application.objects.for_detail()`, `Document.objects.for_owner()`,
  `Simulation.objects.for_dashboard()`) shape graphs explicitly and are locked
  with `assertNumQueries` (see below on prefetching).
- **Persistent onboarding**: a `BorrowerProfile` (one-to-one with the user)
  stores the chosen help office and the phone-verification flag, so those
  onboarding choices survive logout rather than living only in the session.
- **Async** via `django-tasks` (durable database backend, `db_worker`).
- **AI document analysis** runs behind one `analyze_document` function with
  three interchangeable backends, selected by `DOCUMENT_ANALYZER_BACKEND`
  (or auto-resolved): `stub`, `sdk`, and a dev-only `cli`. All three return the
  same result shape, and malformed output is rejected rather than silently
  recorded as an "other" classification. The `sdk` system prompt carries a
  `cache_control` breakpoint so the API can reuse it once it crosses the
  model's cache minimum. The analyzer is fully tested with no key required
  (deterministic stub + SDK/CLI boundaries mocked); one live round-trip test
  auto-skips unless `ANTHROPIC_API_KEY` is present.

### On automatic prefetching

Django 6.0 ships no built-in automatic related-object prefetching (the 6.0
notes only *remove* some implicit prefetch behaviour). Rather than adopt a
third-party library that would require changing model base classes app-wide and
add a runtime dependency, this project keeps explicit `for_*()` QuerySet methods
and locks the query counts with `assertNumQueries`. The trade-off: a little more
boilerplate per read path, in exchange for queries that are visible at the call
site and no production dependency.

### Scope notes

- `IncomeLine.borrower_index` is captured by the model but not yet surfaced in
  the UI; it leaves room for a future per-borrower income breakdown.
- The apply flow wires the BUY purpose end to end; the other purposes share the
  same machinery and are intentionally left as a thin extension point.

## Run locally

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

Optional async worker (documents analyze inline without it in dev):

```bash
uv run python manage.py db_worker
```

## Configuration (12-factor)

Every deploy-sensitive setting is environment-driven; the app runs with all of
them unset for local development. See `.env.example`.

| Variable | Default | Notes |
|---|---|---|
| `SECRET_KEY` | insecure dev key | **Required in production** — a system check fails startup if the default key is used with `DEBUG=False`. |
| `DEBUG` | `True` | Set `False` in production. |
| `ALLOWED_HOSTS` | `*` when `DEBUG` | Comma-separated. |
| `CSRF_TRUSTED_ORIGINS` | empty | Comma-separated `https://…` origins for the deployed host. |
| `MEDIA_ROOT` | `./media` | Point at a persistent volume in production. |
| `SQLITE_PATH` | `./db.sqlite3` | Point at a persistent volume in production. |
| `ANTHROPIC_API_KEY` | unset → stub | Unset keeps the deterministic, free stub analyzer; set it to enable the `sdk` backend. |
| `DOCUMENT_ANALYZER_BACKEND` | auto | `stub`, `sdk`, or `cli`. Empty resolves to `sdk` when a key is present, else `stub` — never `cli`. |
| `CLAUDE_CLI_PATH` | `claude` | Name/path of the `claude` binary for the dev-only `cli` backend. |

### Document analyzer backends

`analyze_document` has three interchangeable backends, all returning the same
result shape:

- **`stub`** — deterministic, offline, no key. The default for tests, CI, and
  the demo deployment. It echoes the application's own data so a document never
  spuriously flags as a mismatch.
- **`sdk`** — the Anthropic Messages API (the production live path). Selected
  automatically when `ANTHROPIC_API_KEY` is set.
- **`cli`** — a **dev-only convenience backend** that shells out to the
  `claude` CLI in print mode (`claude -p … --output-format json`), reusing the
  developer's existing Claude Code login so no API key is needed locally. It is
  **opt-in only** (`DOCUMENT_ANALYZER_BACKEND=cli`) and is **never** the default
  resolution: a deployed container has no `claude` binary, so it must not be
  used in production. If selected without the binary on `PATH`, it fails with a
  clear error rather than silently degrading.

## Production install

teatree is a **dev-only** dependency (it powers the `t3` overlay and is never
imported by the Django app). A production install excludes it:

```bash
uv sync --no-dev          # runtime deps only, no teatree
uv run python manage.py migrate
uv run gunicorn config.wsgi
```

## Quality

```bash
uv run ruff check . && uv run ruff format --check .
uv run ty check portal config
uv run pytest                 # >= 95% coverage gate
```

Pre-commit hooks (`prek install`) run ruff, gitleaks, hygiene checks, and a
pre-push `ty` + `pytest` gate.

## teatree overlay

The repo ships a *lightweight* [teatree](https://github.com/souliane/teatree)
overlay (`overlay/overlay.py`, registered via a `teatree.overlays` entry point)
so the project can be developed and reviewed through the `t3` CLI. It only
teaches teatree where the repo lives, how to run its tests/lint/serve, and how
to validate PR titles (conventional commits). It intentionally does not bundle
lifecycle skills, workspace orchestration, or loop slots — those keep teatree's
defaults. teatree is a dev-only dependency and is never imported by the Django
app at runtime.
