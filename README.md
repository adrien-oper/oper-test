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
- **AI** via the Anthropic SDK with prompt caching, fully unit-tested against a
  mock and **env-gated**: with no `ANTHROPIC_API_KEY` the analyzer returns a
  deterministic, clearly-labelled stub.

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

## Quality

```bash
uv run ruff check . && uv run ruff format --check .
uv run ty check portal config
uv run pytest                 # >= 95% coverage gate
```

Pre-commit hooks (`prek install`) run ruff, gitleaks, hygiene checks, and a
pre-push `ty` + `pytest` gate.
