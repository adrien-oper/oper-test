# Cost & Feasibility Report

This is the report the take-home brief calls its "real point": what this build
actually cost, what it *would* have cost on a metered API key, and the verdict
on whether a candidate can ship it under a $50 Anthropic budget or needs a
temporary Claude Max plan instead.

**One-line answer:** the entire portal — scaffold, FSM domain core, HTMX flow,
sign-up/onboarding, apply flow, document upload, the AI analyzer (built real,
deployed stubbed), Fly deployment, Playwright E2E, the teatree overlay, and a
full bug-hunt + hardening pass — was built on a **Claude Max plan** (flat
monthly fee, no metered token bill). Converted to **API-equivalent** spend at
current Anthropic pricing, the build lands around **$45–75**. A $50 metered key
is on the knife's edge: realistic for a disciplined run, easy to blow past once
you add live debugging and a few re-plans. A temporary Max plan is the
lower-stress choice for a candidate.

> **How to read the numbers.** This build ran on a Max plan, so there is **no
> metered invoice to quote** — every dollar figure here is an *API-equivalent
> estimate*, reconstructed from (a) the per-PR token notes already recorded in
> the commit messages and (b) reasonable extrapolation for the un-instrumented
> commits, priced at the rates in the table below. Estimates are labelled as
> such; nothing here is a real bill.

## 1. Pricing basis (Anthropic, May 2026)

Per million tokens (MTok), first-party Claude API, global routing:

| Model | Input | 5-min cache write | Cache read (hit) | Output |
|---|---|---|---|---|
| Claude Opus 4.x | $5.00 | $6.25 | $0.50 | $25.00 |
| Claude Sonnet 4.6 | $3.00 | $3.75 | $0.30 | $15.00 |
| Claude Haiku 4.5 | $1.00 | $1.25 | $0.10 | $5.00 |

Prompt caching: a cache read costs **10%** of base input; a 5-minute cache
write costs **1.25×** base input. The portal's own AI feature puts a
`cache_control` breakpoint on its static system prompt for exactly this reason
(see `portal/ai/analyzer.py`). Source: Anthropic pricing docs (see *Sources*).

This build was driven mostly by an **Opus-class** coding model, so the
estimates below price tokens at Opus rates — the conservative (most expensive)
choice. A Sonnet-driven run would be about 40% cheaper on the same token volume.

## 2. Token usage and API-equivalent cost

Token counts come from the per-PR notes recorded in the commit messages where
they exist, and are estimated for the rest. The build is heavily **read-heavy**
(reading existing files, test output, diffs), and an agentic coding loop reuses
a large cached context across tool calls — so cache reads dominate input volume
and the *effective* input rate is far below the $5/MTok headline.

### 2a. Reconstructed per-phase estimate (API-equivalent, Opus rates)

| Phase | Tokens (est.) | API-equiv (est.) | Source |
|---|---|---|---|
| Scaffold + FSM domain core + HTMX flow + apply/document + AI analyzer (through PR #2) | ≈1.2M | **≈$20** | commit note: "Build cost so far: ≈$20 (≈€19, ≈1.2M tokens, est.)" |
| Profile/admin/prefetch, E2E suite, overlay rename, input hardening, queue-drain (PRs #3–#7) | ≈0.7M | ≈$11 | estimated (un-instrumented commits) |
| Negative-amount guard (PR #8) | ≈0.5M | ≈$8 | commit note: "≈$8 in tokens + ≈20 min human framing" |
| Analyzer permanent-error fix (PR #9) | ≈0.4M | ≈$6 | commit note: "≈$6 in tokens (incl. live browser exercise)" |
| Dashboard dead-CTA fix (PR #10) | ≈0.3M | ≈$5 | commit note: "≈$5 in tokens" |
| **This hardening pass** (bug-hunt audit fold-in, overlay build-out, COST + README, deploy verify) | ≈0.6–1.6M | **≈$10–25** | estimated (read-heavy audit + multi-file edits + deploy) |
| **Total** | **≈3.7–4.7M** | **≈$60–75 (conservative)** | sum |

The per-fix notes (≈$5–8 each) are themselves Opus-rate estimates of a *small*
focused change; the hardening pass is wider (16 findings, an overlay package, a
cost report, a README, two test suites touched, a redeploy), so its range is
the widest single line.

### 2b. Sensitivity — the headline range

The total swings on two levers the estimates can't pin down precisely:

- **Model.** Opus rates give the ≈$60–75 figure above. The same token volume on
  **Sonnet 4.6** would be **≈$36–45**.
- **Cache efficiency.** The phase numbers price tokens at blended rates. If the
  agentic loop's cache-hit ratio is high (most of a long session's input is
  re-read cached context at $0.50/MTok, not fresh input at $5/MTok), the true
  cost lands at the **low end (≈$45)**. A low cache-hit run with lots of
  full-file re-reads pushes toward the **high end (≈$75)**.

So the honest band is **≈$45 (Sonnet / cache-efficient) to ≈$75 (Opus /
cache-poor)**, centring around **$55–65** for the Opus-driven run this actually
was.

## 3. Wall-clock vs. active build time

- **Wall-clock:** the project spanned a few sittings across roughly **2–3
  calendar days** (the merged PRs #1–#10, then this hardening pass; one long
  stretch of that window was an environment block, see below).
- **Active build time (agent working):** on the order of **4–6 hours** of the
  agent actually generating and running code, dominated by test runs, the live
  browser exercises that found PR #8/#9/#10, and the deploy round-trips.
- **Active *human* time:** small — framing the task, the deploy-account
  decision, and oversight. The per-PR notes record figures like "≈20 min human
  framing/oversight"; summed across the build, human hands-on time is roughly
  **1–2 hours**, mostly review and unblocking, not authoring.

One caveat that inflates wall-clock without inflating cost: this hardening pass
hit a tooling deadlock (a stale skill-routing alias blocked all edits until a
one-line config fix) that cost calendar time but burned almost no tokens.

## 4. The $50-key vs. Max-plan verdict

**Is a $50 metered API key realistic for this assignment?** Borderline — yes if
disciplined, no with any margin for trouble:

- The *happy-path* build (plan → implement → test → ship, little live
  debugging) on **Sonnet with good cache reuse** fits comfortably under $50
  (≈$36–45 estimated).
- The *real* build — which included live browser debugging (the bugs in #8/#9/
  #10 were only found by exercising the deployed app), a few re-plans, and a
  wide hardening pass — on **Opus** runs **≈$55–75**, i.e. **over $50**.
- A metered key also adds *operational anxiety*: a candidate watching a depleting
  balance will avoid the very things that made this build good (running the full
  suite often, exercising the live app, an adversarial bug-hunt). That pressure
  degrades quality precisely where it matters.

**What a candidate can realistically ship under $50 (metered):** a working
single-flow portal with the FSM domain core, the HTMX simulation→apply→upload
journey, the AI analyzer built-and-mocked behind a stub, a green test suite, and
a deploy — i.e. **most of this**, *if* they pick Sonnet, lean on prompt caching,
avoid long live-debugging loops, and don't re-architect mid-stream. The parts
that pushed *this* build over $50 were the live-app debugging and the
adversarial hardening pass — valuable, but the first things to trim under a hard
budget.

**Recommendation:** for a take-home of this size, a **temporary Claude Max
plan** is the better candidate experience. It removes the metering anxiety, lets
the candidate run tests and exercise the live app freely (which is where the
real bugs surfaced here), and costs the issuer a predictable flat fee instead of
a variable bill that a candidate could unintentionally run up. A $50 key works
as a *floor* — enough to ship a solid core — but it quietly taxes the behaviours
that separate a good submission from a great one.

## 5. Hosting cost (separate from the token budget)

One thing worth separating out: the **≈$50 figure above is an Anthropic
API-token budget for *building* the portal**, not what it costs to *host* it.
Running the live demo is a different, much smaller line item — and it has a
catch worth flagging.

This demo deploys to **Fly.io** as a single small Machine plus a volume (see
[`DEPLOY.md`](DEPLOY.md)). At current Fly pricing:

- A `shared-cpu-1x` Machine with 256MB RAM is **≈$2/month** always-on (**≈$6/month**
  at 1GB RAM).
- A persistent volume is **$0.15/GB per month** (this demo uses 1GB).
- Fly's auto-stop suspends an idle Machine, so a demo that mostly sits unused
  drops its compute cost toward **≈$0** — you mainly keep paying for the volume.

So hosting is on the order of **a few dollars a month**, trivially small next to
the build's token cost. The catch is the entry barrier, not the price: **new Fly
organizations have no free tier, and a credit card is required on file just to
deploy at all.** That is easy to forget when planning a take-home — the build
budget and the hosting account are two separate prerequisites, and the second
one needs a payment card before a single `fly deploy` will run.

## Sources

- [Anthropic API pricing (platform.claude.com)](https://platform.claude.com/docs/en/about-claude/pricing)
- [Fly.io pricing (fly.io/docs/about/pricing)](https://fly.io/docs/about/pricing/)
- Per-PR API-equivalent token notes recorded in this repo's commit messages
  (PRs #2, #8, #9, #10).
