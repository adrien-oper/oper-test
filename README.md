# Borrower Portal

A minimal white-label mortgage borrower portal with AI document analysis.
Server-rendered Django 6 + HTMX, no SPA, single-repo monolith.

Live demo: https://borrower-portal-demo.fly.dev/

## What it does

End to end, anonymous simulation through to an AI-analysed document upload:

1. **Simulate** (anonymous, no login) — purpose, number of borrowers, project
   details, contribution, income and expenses (add-row UI) → a feasibility
   report (loan amount, monthly payment, duration, rate) with affordability
   sliders you can drag to see whether the property is within reach.
2. **Sign up** — username + password + privacy-policy acceptance → a stubbed
   phone-number verification → pick a help office. The help office and the
   verification flag persist on a `BorrowerProfile`, so they survive logout.
3. **Dashboard** — your saved simulations; start another or apply on one.
4. **Apply** — recap the simulation, convert it into an application (a guarded,
   atomic state transition), fill a multi-step form (property, applicant
   details, contribution, address, employment, incomes), submit; the dashboard
   then shows the application status.
5. **Documents** — upload a supporting document linked to the application. An
   async task classifies it, extracts key fields, and flags mismatches against
   the application data.

## What I intentionally did NOT build (and why)

The brief and the reference walkthrough repeatedly bless cutting scope, so these
are deliberate omissions, not oversights:

- **Only the BUY purpose is wired end to end.** The other purposes share the
  same machinery and are left as a thin extension point — building all of them
  would add UI surface without exercising any new domain logic.
- **No real phone verification, email, or payment flow.** Phone verification is
  a stub; the walkthrough explicitly says detailed pay flows are not needed.
- **No per-borrower income breakdown in the UI.** `IncomeLine.borrower_index`
  is captured by the model but not surfaced — it leaves room for the feature
  without committing to its UI now.
- **No automatic related-object prefetching library.** Django 6.0 ships none,
  and a third-party one would force model-base-class changes app-wide plus a
  runtime dependency. I kept explicit `for_*()` QuerySet methods instead (see
  *Trade-offs*).
- **AI analysis is built for real but deployed stubbed** (see *AI document
  analysis*) — I have no metered API key, only a Max plan, so the live SDK path
  is implemented and tested but off by default.

## Architecture

- **Django 6 + HTMX**, server-rendered templates, SQLite, single repo.
- **Guarded state machines** (`django-fsm-2`, `protected=True`) model every
  lifecycle — no status field is ever written by hand:
  - `Simulation`: `draft → completed → converted`
  - `Application`: `draft → submitted → under_review → approved | rejected`
    (transitions carry permission guards via `has_transition_perm`)
  - `Document`: `uploaded → analyzing → analyzed | flagged | failed`
  - Simulation → application conversion is itself a guarded, atomic transition.
- **Fat models**: affordability maths, transitions and conversion live on models
  and a pure `affordability` engine, never in views. QuerySet methods
  (`Application.objects.for_detail()`, `Document.objects.for_owner()`,
  `Simulation.objects.for_dashboard()`) shape query graphs explicitly and are
  locked with `assertNumQueries`.
- **Object-level access is scoped once** through `get_owned_or_404`. Uploaded
  files carry PII, so they are served only through the authenticated,
  owner-scoped `document_file` view — never a public static-media route.
- **Async** via `django-tasks` (durable database backend, `db_worker`). The
  analysis task is idempotent and enqueued only after the upload transaction
  commits (`transaction.on_commit`); it re-claims stranded `uploaded`/
  `analyzing` rows under a row lock on restart, so it resumes safely.
- **AI document analysis** runs behind one `analyze_document` function with
  three interchangeable backends (`stub`, `sdk`, dev-only `cli`), selected by
  `DOCUMENT_ANALYZER_BACKEND` or auto-resolved. All return the same result
  shape; malformed model output is rejected, not silently recorded. The `sdk`
  system prompt carries a `cache_control` breakpoint so the API can reuse it
  once it crosses the model's cache minimum. The whole analyzer is unit-tested
  with no key required (deterministic stub + SDK/CLI boundaries mocked); one
  live round-trip test auto-skips unless `ANTHROPIC_API_KEY` is present.

## Run locally

```bash
uv sync
uv run python manage.py migrate && uv run python manage.py runserver
```

Documents analyze inline in dev, so no worker is needed. To exercise the durable
queue path, run the worker alongside the server:

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
- **`cli`** — a dev-only convenience backend that shells out to the `claude` CLI
  in print mode, reusing the developer's existing Claude Code login so no API
  key is needed locally. Opt-in only (`DOCUMENT_ANALYZER_BACKEND=cli`), never
  the default resolution, and never available in a deployed container (no
  `claude` binary). It fails with a clear error rather than silently degrading.

## Trade-offs (deliberate)

- **Explicit `for_*()` QuerySet methods over an auto-prefetch library** —
  a little more boilerplate per read path, in exchange for queries that are
  visible at the call site, locked by `assertNumQueries`, and no runtime
  dependency.
- **Single-host SQLite + co-located worker over Postgres/LiteFS** — the demo is
  one Fly Machine with the queue in the SQLite file on the volume, so the worker
  runs co-located with gunicorn (under a restart loop in the entrypoint). Simple
  and cheap to run (a single small Machine, a few dollars a month — see the
  *Hosting cost* note in [`COST.md`](COST.md)); the cost is that a separate worker
  Machine or multi-region needs Postgres/LiteFS first (see `DEPLOY.md`). The analysis task
  is resumable, so a restart drains any backlog.
- **AI built real, deployed stubbed** — the SDK path with prompt caching is
  implemented and unit-tested, but the demo runs the free deterministic stub so
  it incurs no metered API spend.

## Production install

teatree is a **dev-only** dependency (it powers the `t3` overlay and is never
imported by the Django app). A production install excludes it:

```bash
uv sync --no-dev          # runtime deps only, no teatree
uv run python manage.py migrate
uv run gunicorn config.wsgi
```

Deployment to Fly.io (remote build, no local Docker) is documented in
[`DEPLOY.md`](DEPLOY.md).

## Quality

```bash
uv run ruff check . && uv run ruff format --check .
uv run ty check portal config
uv run pytest                 # >= 95% coverage gate
```

Pre-commit hooks (`prek install`) run ruff, gitleaks, hygiene checks, and a
pre-push `ty` + `pytest` gate. End-to-end Playwright coverage of the core
journeys lives under `e2e/` (run with `uv run --group e2e pytest e2e --no-cov`).

## teatree reuse

This repo reuses [teatree](https://github.com/souliane/teatree), an open-source
agent CLI, in two honest ways:

- **Skills + copied config.** The project's tooling baseline (ruff/ty/pytest
  config, prek hooks, the `uv`/Django-oriented `pyproject` shape) was adapted
  from teatree's stack rather than reinvented, and the `ac-django` / `ac-python`
  skills guided the code style.
- **A teatree overlay.** `overlay/overlay.py` registers via a `teatree.overlays`
  entry point so the project can be developed, provisioned, run, tested, and
  reviewed through the `t3` CLI. It teaches teatree where the repo lives, how to
  run its test/lint/format/typecheck/serve/worker commands, how to provision a
  worktree (sync + migrate, AI stubbed by default), how to validate PR titles
  (conventional commits), and which companion skills to load (`ac-django`,
  `ac-python`, and a small project skill in `.claude/skills/borrower-portal/`).
  It deliberately omits multi-tenant DB orchestration, loop slots, and messaging
  backends — those do not apply to a single-repo SQLite project. teatree stays a
  dev-only dependency, never imported by the Django app at runtime.

### Install the overlay into an existing `t3`

If you already run teatree's `t3` (installed as a `uv` tool), register this
overlay's entry point alongside it with one command — no separate `t3`, and the
existing teatree install stays editable from its own checkout:

```bash
uv tool install teatree --with-editable /path/to/oper-test
```

Verify the entry point is discovered:

```bash
t3 info | grep borrower-portal          # lists config.settings + the repo path
python -c "from importlib.metadata import entry_points; \
  print([e.value for e in entry_points(group='teatree.overlays') if e.name=='borrower-portal'])"
# -> ['overlay.overlay:BorrowerPortalOverlay']
```

The overlay also reads an `[overlays.borrower-portal]` table in `~/.teatree.toml`
(`path`, `protected_branches`, `mode`) for per-machine settings.

### What the overlay drives

The overlay implements the `OverlayBase` hooks that back the full local dev
lifecycle — these are the exact commands used to verify it:

```bash
t3 borrower-portal worktree smoke-test    # overlay loads, CLI/DB/hooks/imports OK
t3 borrower-portal workspace ticket <url> # create ticket + git worktree
t3 borrower-portal worktree provision     # uv sync + migrate into the worktree DB
t3 borrower-portal run tests              # the portal pytest suite (95% gate)
t3 borrower-portal run verify             # probe the verify endpoints (/, /dashboard/, /admin/login/)
t3 borrower-portal ticket clear … / merge # the sanctioned review→merge keystone
```

`provision` runs the portal's own `manage.py` in a clean environment pinned to
`config.settings`, so the worktree's SQLite file and migrations stay the
portal's — teatree's control database is never touched. The lifecycle is driven
through teatree's core commands (`python -m teatree …`); a teatree-side dispatch
gap that routes these FSM groups to a lightweight overlay's `manage.py` is noted
in the follow-up PR.

## AI-usage note

This portal was built with Claude Code (Claude Opus-class models) on a Claude
Max plan, used as a pair-programmer across planning, implementation, tests, and
this documentation.

Where I stopped trusting the AI and verified by hand:

- **State-machine and permission boundaries** — I checked every `@transition`
  guard and the conversion path myself rather than trust generated transitions,
  since a wrong guard is a silent authorization hole. (One such hole — a borrower
  rewriting identity fields on an already-submitted application — was found and
  closed in the hardening pass.)
- **The async task's idempotency and resumability** — the row-lock + re-claim
  logic and the after-commit enqueue were reviewed against the actual failure
  modes (worker restart mid-analysis), not accepted on first generation.
- **Query counts** — every `for_*()` QuerySet method is pinned with
  `assertNumQueries`, because generated ORM code is prone to quiet N+1s.
- **The AI analyzer's failure handling** — malformed model output, bad keys,
  and unknown models are explicitly tested, since the one component calling an
  LLM is the least deterministic.
- **Security and deploy hardening** — the `SECRET_KEY`/`DEBUG` startup check,
  object-level ownership checks, the PII-document download path, and file-upload
  validation were verified against an adversarial checklist rather than assumed.

Rough human time: on the order of **1–2 hours** hands-on (framing, the
deploy-account decision, review and unblocking), against roughly **4–6 hours**
of active agent build time over 2–3 calendar days. This exercise was built
inside a larger multi-task Claude Code session, so exact cost attribution is
imprecise (±50%). Measured via `ccusage` (browser and image tokens included),
the API-equivalent spend is **approx. $310 (range $100–$620)** for the exercise
alone and **approx. $450 (range $160–$800)** including the supporting teatree
tooling. A clean from-scratch build of just the portal would realistically cost
**approx. $75–$100** — so a $50 metered key is optimistic and likely short; a
temporary Max plan is the lower-stress choice. The per-scope breakdown,
wall-clock vs. active time, and the budget verdict are in the **[Cost &
Feasibility Report](COST.md)**.
