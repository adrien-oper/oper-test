# Cost & Feasibility Report

This is the report the take-home brief calls its "real point": what this build
actually cost, what it *would* have cost on a metered API key, and the verdict
on whether a candidate can ship it under a $50 Anthropic budget or needs a
temporary Claude Max plan instead.

**One-line answer:** the entire portal — scaffold, FSM domain core, HTMX flow,
sign-up/onboarding, apply flow, document upload, the AI analyzer (built real,
deployed stubbed), Fly deployment, Playwright E2E, the teatree overlay, and a
full bug-hunt + hardening pass — was built on a **Claude Max plan** (flat
monthly fee, no metered token bill). The session logs carry real per-message
token counts, so this is **measured, not estimated**: **≈19.9M tokens, ≈96%
cache reads**, priced at **Opus** rates → an **API-equivalent ≈$19–20** (honest
band $18–25; on **Sonnet** rates ≈$11–13). A **$50 metered Opus key is
comfortably sufficient** — about **2.5× headroom**. The reason the two numbers
look so far apart: an agentic loop re-reads a large *cached* context on every
turn, so token **volume** is high while the **effective** cost stays low (a
cache read is one-tenth the price of fresh input).

> **How to read the numbers.** The dollar figures here are an *API-equivalent*
> reconstruction — this build ran on a Max plan, so there is no metered invoice
> — but the **token counts are measured**, taken from the session telemetry
> (per-message usage deduped by `message.id`, validated against `ccusage`), then
> priced at the published rates in the table below. So the *volume* is real; only
> the *pricing* is a conversion.

## 1. Pricing basis (Anthropic, verified 2026-05-29)

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

This build was driven mostly by an **Opus-class** coding model, so the figures
below price the measured token volume at Opus rates — the more expensive of the
two. The same tokens on **Sonnet** rates come out about 40% cheaper (≈$11–13).

## 2. Token usage and API-equivalent cost

The build's two sessions hold real per-message usage. Deduped by `message.id`
and summed, the whole build is:

| Measurement | Value |
|---|---|
| Total tokens | **≈19.9M** (19,880,179) |
| Cache read | **95.8%** |
| Cache write | **2.9%** |
| Output | **1.2%** |
| Fresh input | **0.1%** |
| **API-equivalent (Opus rates)** | **≈$19–20** (band $18–25) |
| API-equivalent (Sonnet rates) | ≈$11–13 |

That is one measured line, not a sum of estimates:

> **≈19.9M tokens, 95.8% cache-read / 1.2% output → ≈$19–20 Opus
> API-equivalent, measured from session telemetry.**

The reason the dollar figure is low against a 19.9M-token volume is the mix.
Almost all of it is cache reads at $0.50/MTok, so the **effective blended rate
is ≈$0.96/MTok** — roughly a fifth of the $5/MTok *input* headline. An agentic
coding loop re-reads a large cached context on every turn, which inflates token
*volume* but not cost.

### 2a. Per-PR cost notes (estimates, not summed)

The commit messages record rough per-PR figures. They are kept here for what
each change cost on its own, but are explicitly **not** added up into the build
total: summing them double-counts (the early note already covers the scaffold
the later fixes build on), and they priced tokens near the fresh-input rate,
which the measured cache-read-dominant mix shows is not what happened.

| PR | Note | Estimate |
|---|---|---|
| #8 — negative-amount guard | "≈$8 in tokens + ≈20 min human framing" | ≈$8 |
| #9 — analyzer permanent-error fix | "≈$6 in tokens (incl. live browser exercise)" | ≈$6 |
| #10 — dashboard dead-CTA fix | "≈$5 in tokens" | ≈$5 |
| #2 — scaffold through AI analyzer (broad phase, not a single fix) | "Build cost so far: ≈$20 (est.)" | ≈$20 |

The measured **≈$19–20 total** is the number that governs the budget; the per-PR
notes just show the rough shape of where effort went.

### 2b. Sensitivity — why the cost stays low

The measured cost barely moves on the two levers that matter, because the cache
mix is so lopsided:

- **Model.** Opus rates give **≈$19–20**. The same token volume on **Sonnet**
  rates is **≈$11–13**.
- **Cache efficiency.** A blended rate above $5/MTok is *arithmetically
  impossible* with this mix — cache reads ($0.50) and output are most of the
  bill, so no realistic run lands near the old fresh-input-priced estimate. Even
  a pessimistic **90% cache-hit** (vs. the ≈96% this build ran) is only
  **≈$25–28** on Opus. Opus crosses **$50** only if cache-hit falls below
  **≈62%** of input-side tokens — far outside anything an agentic loop produces.

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

**Felt usage vs. metered cost.** These are two different measurements, and both
are true. The token *volume* was high — ≈19.9M, more than a naive estimate — so
on a Max plan it *feels* like fast consumption (it's rate-limit pressure you
notice, not a dollar meter). The metered *dollar* cost is low all the same,
because cache reads dominate the mix. High volume and low cost are not in
tension here; they are just answers to different questions.

## 4. The $50-key vs. Max-plan verdict

**Is a $50 metered Opus key enough for this assignment?** **Yes, comfortably.**
The measured cost is **≈$19–20** on Opus (≈$11–13 on Sonnet) — about **2.5×
headroom** under $50.

- The whole build fits, including the parts that look expensive. The live-app
  debugging (the bugs in #8/#9/#10 were only found by exercising the deployed
  app) and the adversarial hardening pass are *in* the ≈$19–20 — they did **not**
  push it over $50.
- Opus crosses $50 only if the cache-hit ratio falls **below ≈62%** of
  input-side tokens. This build ran at **≈96%**, and an agentic coding loop —
  which re-reads the same cached context turn after turn — stays cache-heavy by
  construction. Even a pessimistic 90% cache-hit is only ≈$25–28.

**A temporary Max plan remains a reasonable option** — a flat fee removes the
meter entirely and the rate limits are generous — but it is **no longer required
to make the budget work**. A $50 Opus key covers the full build, the live
debugging, and the hardening pass with room to spare; the choice between metered
and Max is now about preference (flat fee, no balance to watch), not necessity.

## 5. Hosting cost (separate from the token budget)

One thing worth separating out: the **≈$19–20 figure above is an Anthropic
API-token cost for *building* the portal**, not what it costs to *host* it.
Running the live demo is a different line item — and it has a catch worth
flagging.

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
- **Token volume:** measured from the build's session telemetry — per-message
  usage deduped by `message.id` across the two sessions, validated against
  [`ccusage`](https://github.com/ryoppippi/ccusage). The dollar figures convert
  that measured volume at the published rates above.
- Per-PR cost notes in this repo's commit messages (PRs #2, #8, #9, #10) are
  kept as per-change estimates only, not summed into the build total.
