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
  lives on models and a pure `affordability` engine, not in views.
- **Async** via `django-tasks` (durable database backend, `db_worker`).
- **AI** via the Anthropic SDK, fully unit-tested against a mock and
  **env-gated**: with no `ANTHROPIC_API_KEY` the analyzer returns a
  deterministic, clearly-labelled stub. The static system prompt carries a
  `cache_control` breakpoint so the API can reuse it once it crosses the
  model's cache minimum. Malformed model output is rejected, not silently
  recorded as an "other" classification.

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
| `ANTHROPIC_API_KEY` | unset → stub | Unset keeps the deterministic, free stub analyzer; set it to enable live analysis. |

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
