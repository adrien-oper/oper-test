---
name: borrower-portal
description: Project conventions for the borrower-portal repo — the white-label mortgage portal (Django 6 + HTMX + django-fsm-2 + django-tasks). Use when implementing, reviewing, or debugging anything in this repo so the FSM, fat-model, and AI-analyzer conventions are followed. Load alongside ac-django and ac-python.
compatibility: This repo only (adrien-oper/oper-test). Requires Python 3.13+, uv, Django 6.
metadata:
  version: 0.1.0
  subagent_safe: true
---

# Borrower Portal — project conventions

A minimal white-label mortgage borrower portal with AI document analysis.
Server-rendered Django 6 + HTMX, SQLite, single-repo monolith. This skill
captures the repo-specific rules that `ac-django` / `ac-python` do not.

## Golden rules (do not break these)

1. **Status is never a bare field write.** Every lifecycle is a guarded
   `django-fsm-2` `FSMField(protected=True)`. Change state only through a
   `@transition` method, never by assigning `obj.state = ...`.
   - `Simulation`: `draft → completed → converted`
   - `Application`: `draft → submitted → under_review → approved | rejected`
   - `Document`: `uploaded → analyzing → analyzed | flagged | failed`
   - Simulation → application conversion is itself a guarded, atomic transition
     (`Application.create_from_simulation`).
   When you need a precondition, add it as a transition `condition`/`permission`,
   not an `if` in the view.

2. **Fat models, thin views.** Affordability maths, transitions, and conversion
   live on models and the pure `portal/affordability.py` engine. Views only
   coordinate (fetch the owned object, bind a form, call a transition, render).

3. **Ownership is scoped once.** Object-level access goes through
   `portal/views/_shared.py::get_owned_or_404` (or `Document.objects.for_owner`).
   Never `get_object_or_404(Model, pk=pk)` without an owner filter on a
   borrower-facing view. Uploaded files (PII) are served only through the
   authenticated `portal:document_file` view — never a public static-media route.

4. **Async work is idempotent and after-commit.** Document analysis is enqueued
   with `transaction.on_commit(... .enqueue(pk))` and the task re-claims
   stranded `uploaded`/`analyzing` rows under a row lock, so a worker restart
   resumes safely. Split terminal failures (bad output, unsupported type,
   permanent backend error) from transient ones (let those retry).

5. **AI runs behind one function, three backends.** `portal/ai/analyzer.py`
   exposes `analyze_document`; backends are `stub` (default, offline,
   deterministic), `sdk` (Anthropic Messages API with a `cache_control` prompt
   breakpoint), and a dev-only `cli`. Resolution is auto (`sdk` when a key is
   set, else `stub`) — never default to `cli`. All three return the same
   `AnalysisResult`; reject malformed model output, never record a bogus
   classification.

## Quality bar

- `uv run ruff check .` and `uv run ruff format --check .` clean.
- `uv run ty check portal config` clean.
- `uv run pytest` green at ≥ 95% coverage (`tests/` only; `e2e/` runs with
  `--no-cov`).
- TDD: a fix gets a regression test that fails on the bug first.

## Running through the t3 overlay

The repo registers a lightweight teatree overlay (`overlay/overlay.py`), so:

```bash
t3 borrower-portal run test     # uv run pytest
t3 borrower-portal run lint     # uv run ruff check .
t3 borrower-portal run serve    # uv run python manage.py runserver
```

teatree is a dev-only dependency and is never imported by the Django app.
