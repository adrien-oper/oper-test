# Cost & Feasibility Report

This is the report the take-home brief calls its "real point": what this build
actually cost, what it *would* have cost on a metered API key, and the verdict
on whether a candidate can ship it under a $50 Anthropic budget or needs a
temporary Claude Max plan instead.

**One-line answer:** the portal — scaffold, FSM domain core, HTMX flow,
sign-up/onboarding, apply flow, document upload, the AI analyzer (built real,
deployed stubbed), Fly deployment, Playwright E2E, an in-browser bug-hunt, and a
hardening pass — was built on a **Claude Max plan** (flat monthly fee, no
metered token bill). Two API-equivalent figures, both at Opus rates:

- **Exercise only** (just this portal: the PRs, the in-browser bug-hunt, the
  deploy round-trips): **approx. $310**, range **$100–$620**. Browser and image
  tokens for the live debugging are **already included** in this figure, not
  added on top.
- **Exercise + supporting [teatree](https://github.com/souliane/teatree)
  tooling** (the portal plus the overlay/plumbing work that enabled it):
  **approx. $450**, range **$160–$800**.

These are *attribution estimates at ±50%*, not a metered invoice — the build ran
inside a larger multi-task Claude Code session, so splitting the shared cost
cleanly across tasks is imprecise. The token volume is measured (via `ccusage`);
the per-task split and the dollar conversion carry the uncertainty. **No single
figure here should be read without its range.**

> **How to read the numbers.** This exercise was built inside a larger
> multi-task Claude Code session, so exact cost attribution is imprecise (±50%).
> The figures are API-equivalent — the build ran on a Max plan, so there is no
> metered invoice — reconstructed from `ccusage`-measured token volume (browser
> and image tokens included) and split between "just the portal" and "the
> portal plus the teatree tooling that supported it." Treat every number as the
> centre of its stated range.

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
two. The same tokens on **Sonnet** rates come out roughly 40% lower.

## 2. Token usage and API-equivalent cost

The build ran inside a larger multi-task Claude Code session. The total token
volume across that session is measured via `ccusage`, but it covers more than
this exercise, so the cost attributed to the portal is an estimate: it isolates
the messages and tool calls that belong to this build (and, for the second
figure, the teatree overlay work that supported it) and prices that slice at
Opus rates. Because the session is shared, that slice can only be drawn
approximately — hence the ±50% bands.

### 2a. Per-scope estimate (API-equivalent, Opus rates)

| Scope | API-equivalent (est.) | Range | What it covers |
|---|---|---|---|
| **Exercise only** | **approx. $310** | **$100–$620** | This portal: scaffold through AI analyzer, the merged PRs, the in-browser bug-hunt (PRs #8/#9/#10), Playwright E2E, the deploy round-trips. Browser/image tokens included. |
| **Exercise + teatree tooling** | **approx. $450** | **$160–$800** | The above, plus the [teatree](https://github.com/souliane/teatree) overlay and plumbing built to support this exercise. |

The gap between the two figures (approx. $140) is the supporting-tooling slice: the
overlay package and the workflow plumbing that this exercise leaned on but that
isn't strictly part of the portal itself.

**Browser and image tokens.** The in-browser debugging (exercising the deployed
app to find the bugs behind PRs #8/#9/#10) and the deploy-verification
screenshots cost roughly **$10–12**. Image tokens are expensive and not
cache-friendly, so they are worth calling out — but they are **already counted
inside the approx. $310 exercise-only figure**, not added on top of it.

### 2b. Sensitivity — why the range is wide

The headline figures swing on two things the estimate can't pin down precisely:

- **Attribution.** The build shared a session with other tasks, so the slice
  assigned to the portal (and to the teatree tooling) is drawn by judgement, not
  by a meter. That alone is the ±50% band: the low end assumes a tight slice,
  the high end a generous one.
- **Model.** The figures above are Opus rates. The same token volume on
  **Sonnet** rates lands roughly 40% lower.

A clean, **from-scratch build of just the portal** — no shared-session
overhead, no other tasks interleaved — would realistically cost **approx.
$75–$100** in metered tokens. That is the number to plan a budget against, and
it is why the much larger attribution figures above carry such wide ranges: most
of the apparent cost is shared-session context that a focused, standalone build
would not pay.

## 3. Wall-clock vs. active build time

- **Wall-clock:** the project spanned a few sittings across roughly **2–3
  calendar days** (the merged PRs #1–#10, then this hardening pass; one long
  stretch of that window was an environment block, see below).
- **Active build time (agent working):** on the order of **4–6 hours** of the
  agent actually generating and running code, dominated by test runs, the live
  browser exercises that found PR #8/#9/#10, and the deploy round-trips.
- **Active *human* time:** small — framing the task, the deploy-account
  decision, and oversight. Summed across the build, human hands-on time is
  roughly **1–2 hours**, mostly review and unblocking, not authoring.

One caveat that inflates wall-clock without inflating cost: this hardening pass
hit a tooling deadlock (a stale skill-routing alias blocked all edits until a
one-line config fix) that cost calendar time but burned almost no tokens.

## 4. The $50-key vs. Max-plan verdict

**Is a $50 metered Opus key enough for this assignment?** **Optimistic, and
likely short.**

A clean, from-scratch build of just the portal realistically runs **approx.
$75–$100** in metered tokens (§2b) — so a $50 budget is on the optimistic side
and will probably fall short once you include the things that made this build
good: running the full test suite often, exercising the live app, and an
adversarial bug-hunt. The live-app debugging behind PRs #8/#9/#10 was only
possible by exercising the deployed app, and that work (browser and image
tokens) is real spend.

- A disciplined, happy-path build on **Sonnet** with strong cache reuse could
  squeeze under $50, but with little margin for live debugging or re-plans.
- The build this actually was — Opus, with live browser debugging and a
  hardening pass — exceeds a $50 metered budget for a clean standalone run, and
  by a wide margin once shared-session overhead is attributed in.

**A temporary Max plan is the lower-stress choice for a candidate.** A flat fee
removes the meter entirely, the rate limits are generous, and it lets the
candidate run tests and exercise the live app freely — which is exactly where
the real bugs surfaced here. A $50 key works as a *floor* — enough to ship a
solid core — but it quietly taxes the behaviours that separate a good submission
from a great one.

## 5. Hosting cost (separate from the token budget)

One thing worth separating out: the figures above are an Anthropic API-token
cost for *building* the portal, not what it costs to *host* it. Running the live
demo is a different line item — and it has a catch worth flagging.

This demo deploys to **Fly.io** as a single small Machine plus a volume (see
[`DEPLOY.md`](DEPLOY.md)). At current Fly pricing:

- A `shared-cpu-1x` Machine with 256MB RAM is **approx. $2/month** always-on
  (**approx. $6/month** at 1GB RAM).
- A persistent volume is **$0.15/GB per month** (this demo uses 1GB).
- Fly's auto-stop suspends an idle Machine, so a demo that mostly sits unused
  drops its compute cost toward **approx. $0** — you mainly keep paying for the
  volume.

So hosting is on the order of **a few dollars a month**, trivially small next to
the build's token cost. The catch is the entry barrier, not the price: **new Fly
organizations have no free tier, and a credit card is required on file just to
deploy at all.** That is easy to forget when planning a take-home — the build
budget and the hosting account are two separate prerequisites, and the second
one needs a payment card before a single `fly deploy` will run.

## Sources

- [Anthropic API pricing (platform.claude.com)](https://platform.claude.com/docs/en/about-claude/pricing)
- [Fly.io pricing (fly.io/docs/about/pricing)](https://fly.io/docs/about/pricing/)
- **Token volume:** measured via [`ccusage`](https://github.com/ryoppippi/ccusage)
  across the build's Claude Code session (browser and image tokens included).
  The dollar figures attribute a slice of that volume to this exercise (and, for
  the second figure, the supporting teatree tooling) and convert it at the
  published rates above. Because the session was shared across multiple tasks,
  the per-scope split is an estimate at ±50%, not a metered invoice.
