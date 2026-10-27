# 20 — Incident Management, SLOs, and Error Budgets

**Folder:** `20-incident-slo/`

---

## Teach first: SLIs, SLOs, and why they're the whole game

Reliability is not "it's up." It's **"users are actually served successfully, at the volume they need."** You can't optimize what you can't measure, so SRE starts with metrics:

- **SLI (Service Level Indicator)** — a *measured* quantity: `good_requests / total_requests`, `p99_latency < 500ms`, `uptime`.
- **SLO (Service Level Objective)** — a *target* on an SLI: "99.9% of requests over 30 days succeed."
- **SLA (Service Level Agreement)** — a *contractual* commitment with penalties. You don't need an SLA in a homelab; you need **SLOs** (the target you *manage to*), not SLAs (the legal thing).

> **The L6 reframe — the SLO is a *budget*, not a score.** An SLO of 99.9% over 30 days means you're *allowed* to be wrong ~43 minutes/month. That's your **error budget.** If you've *not* spent it, you're "reliable enough" to ship more features fast. If you've *used* it, you **stop** shipping features and *fix reliability* until the budget regenerates. **The SLO converts "reliability" (vague) into a number that gates *how fast you can change* (concrete).** That's the entire SRE operating loop.

### The error-budget "burn rate"

- **1x burn rate** = on track to *exactly* use the monthly budget. Fine.
- **14x burn rate** = using the *daily* budget as fast as you have it — you'll be *out* in a day. **Page now.**
- **100x burn rate** = out of budget in ~1 minute. This is not a "degraded service," it's an *outage.*

**Deriving "100x = out in ~1 minute" (the arithmetic a panel will ask you to do, not recite):**

Take the monthly budget: 99.9% over 30 days ≈ **43 minutes** of allowed downtime.
- "Out of budget" at burn rate B means you consume the *monthly* 43 min in `43 / B` minutes.
- B = 100 ⇒ 43 / 100 = **0.43 minutes ≈ 26 seconds** to exhaust the *month*. The "~1 minute" is the rounded, memorable version.
- B = 14 ⇒ 43 / 14 ≈ **3 minutes** to burn the month. That's why 14x on a *1h* window is a page: you're on pace to blow the whole month in ~3 min.
- B = 1 (slow) ⇒ 43 min as planned — that's the 6h window ticketing "we'll be out by month-end if unaddressed."

> **The two-window comparison (why *both* windows, the worked example):** a *fast* 1h@14x alert and a *slow* 6h@1x alert give **different answers on the same incident**, and that difference is the whole point.
> - **A sudden outage** (5xx jumping to 30%): the 1h window blows past 14x *immediately* → **page**. The 6h@1x window may still read ~1x because it's *averaging* the last hour with 5 healthy hours → **quiet**. Without the 1h window you'd miss a hard outage for up to 6 hours.
> - **A slow leak** (0.01% extra errors every hour): the 1h window barely moves (≈1.5x, below 14) → **no page**. But it accrues; at 6h the running average crosses 1x → **ticket**. Without the 6h window you'd never catch the bleed, and the 1h window alone would stay silent for *days*.
> - **An alert fires only when *its own* window's burn exceeds its threshold** — the "both windows" phrasing means "I run *two* detectors; each fires on its own window." It's not "both must fire simultaneously." Clarify this in any panel discussion; the simultaneous-AND version would *delay* pages.

> **Threshold — page on multi-window, multi-burn-rate (MWMR).** The Google-recommended alerting: **two windows** (say 1h and 6h) AND **two burn rates** (fast, slow). The 1h window catches outages fast; the 6h window catches slow bleeds. This single design kills the two most common alerting sins: **alerting on a 1-second blip (noise)** and **missing a slow leak (1h window alone wouldn't fire at low burn rates)**. This is the exact mechanism you'll wire into Prometheus Alertmanager (doc 11).

---

## SEVs and escalation (the incident taxonomy)

| SEV | Definition | Burn threshold (on a critical SLI) | Who acts | Response |
|---|---|---|---|---|
| **SEV-1** | Full or near-full outage; SLO catastrophically violated | **≥ 100x** burn (out of monthly budget in <1 min) | On-call engineer + incident commander | Immediate page, drive hard, *stop all other work* |
| **SEV-2** | Major degradation; a *real* user-impacting SLO breach, partial | **≥ 50x** burn (out in ~1 min of the monthly) | On-call | Page, handle now |
| **SEV-3** | Slow leak; trending toward SLO breach | **≥ 1x sustained** on the 6h window (out by month-end) | Next-day handling | Ticket, not page |
| **SEV-4** | Cosmetic / low impact | below burn thresholds; no user impact | Backlog | Track, don't page |

> **The L6 instinct — classify by *SLO burn*, not by *feeling*.** A SEV is not "how scary did that look." It's "did the *error budget* for a critical user-facing SLI cross a burn threshold?" If `outline` login is returning 500s at ~30% error rate, that's ≈ **30× the 0.1% SLO target = 300x burn** → SEV-1 *by the numbers* — not by whether it "feels big." **Tying SEV to SLO burn removes the argument about severity and makes escalation objective.** This is the *measurable* reliability discipline that separates L6 from "we paged because it looked bad."
>
> **Why the numbers above:** with a 99.9% SLO (0.1% allowed error), burn = `actual_error_rate / 0.001`. 50× burn = 5% errors; 100× = 10% errors; 300× = 30% errors (an *outage*). These map cleanly to SEV-2/1/1 respectively. **The mapping is per-SLO** — a 99.5% SLO (0.5% allowed) shifts every threshold down by 5×. *Always compute burn against the SLO you actually set, not against a fixed error rate.*

---

## The incident lifecycle (and the two roles that matter)

```
Detect → Triage (is it real? which SEV?) → Mitigate (stabilize) → Root-cause (postmortem) → Action items
```

Two *roles* (even solo, you play both, and *separating the hats is the lesson*):

- **Incident Commander (IC)** — coordinates. Doesn't *do* the fix; keeps the *room* organized: timeline, comms, deciding when to escalate/rollback, protecting the on-call from doing everything at once.
- **Operator / Fixer** — actually runs the mitigation.

> **The L6 move — an IC is a *process* role, not a tech role.** A senior can be a great engineer who makes a *bad* IC because they jump into fixing and stop coordinating. The IC's job is to **keep the incident *from becoming a swamp***: "who is doing what, what's the plan, what's the next check, when do we stop." If you can be both without losing the coordination thread, you've earned the L6 bar on incident leadership (doc 23 extends this).

### Mitigation before root cause

The *first* goal is **stabilize**, not *diagnose*:

1. **Detect** the symptom (an SLO-burn alert, a user report).
2. **Mitigate** — *any* action that reduces user impact: rollback the last deploy (doc 04/19), shed load, reroute, scale. **You do not need to know the cause to mitigate.**
3. *Then* root-cause, with evidence preserved.

> **Failure mode — "but I want to understand why before I fix it."** This is the #1 junior incident mistake. A broken system's *diagnosis* is unstable (everything is changing). **Stabilize first** (rollback / mitigate), *preserve the failing state* (logs, metrics, core dumps, a repro), *then* debug the preserved state. You can debug a reproducible failure; you can't debug a live, actively-degrading one. This is doc-16's "stabilize, then root-cause" made into a hard rule.

---

## The postmortem (blameless, and the part juniors skip)

After every SEV-1/2, a written postmortem. **Blameless = "the system let this happen; how do we fix the *system* so it can't happen again?"** Not "who clicked it." The structure:

```
## Incident: 2026-10-24 Outline login SEV-2
**Duration:** 34 min. **Error budget impact:** 11% of monthly.
**User impact:** login 500s, ~200 failed attempts.

### Timeline (all times UTC)
14:02 SEV-2 alert: outline login 5xx burn > threshold
14:05 IC paged, mitigation chosen: rollback
14:07 rollback applied
14:19 SLO burn back below 14x
14:36 post-deploy confirmed stable

### Root cause (SYSTEMIC, not "who")
The deploy (13:58) bumped Postgres max_connections down. outline-server's
connection pool overshot the new max_connections → connection-refused → 500s.
The *systemic* gap: we had no guard against a config deploy that lowers a
limit the running app depends on.

### Action items (each concrete + owner + due)
[ ] (done) Add a guard: Helm values change to max_connections requires review
[ ] (due +1d) Alert on active pool > 80% of max_connections (doc 11)
[ ] (due +1w) Load-test the app against Postgres limit (doc 22)
[ ] Document the mitigation in the runbook (doc 16)
```

> **The L6 test of a postmortem: "Did it change the system?"** A postmortem with no closed action items *reproduces the incident.* The measure of an L6 postmortem isn't "we wrote a good document," it's **"the class of failure that just hit us is now structurally impossible"** — a guard, an alert, a limit, or a test was *added* because of it. Every SEV makes the system measurably better or it was a wasted 3am.

---

## The SLO you'll actually define for Outline

Start with **three SLIs** — the SRE "four golden signals" (latency, traffic, errors, saturation), narrowed to what *users* care about:

| SLI | SLO | Why this one |
|---|---|---|
| **Availability** — fraction of requests returning 2xx/3xx | 99.9% / 30d | The primary "is it up" signal |
| **Latency** — p99 of page load / API < 500ms | 99% of requests | Slow-but-working still hurts |
| **Auth success** — OIDC login succeeds (doc 09) | 99.9% | A login failure = total loss of access; *higher* than availability |

> **Threshold — set the SLO to what you *can defend*, not what you *wish*.** 99.999% ("five nines") is the marketing number; it's *very* expensive and it's usually a lie for a homelab. **Pick 99.9% or 99.5% — something you can *measure, hit, and afford* — and make the number explicit.** An unaffordable SLO (an error budget you'll never have) makes the whole system a permanent failure; an affordable one makes the budget *actionable.* This is the most common L5/L6 mistake: a vanity SLO.

### Turning the SLO into alerts (doc 11, MWMR)

For the availability SLO (99.9%/30d ≈ 43 min budget):
- **Fast window (1h):** burn 14x → page ("we're out of budget in ~hours")
- **Slow window (6h):** burn 1x sustained → ticket ("slow bleed; we'll be out by month-end if unaddressed")

**The alert *is* the SLO expressed as a threshold.** This is the link between doc 11 (metrics) and this doc (reliability): **your alerts should be SLO-burn alerts, not "CPU is high" alerts.** A "CPU high" alert pages you; an "availability SLO at 14x burn" alert tells you *the user is affected and here's how fast.*

---

## The workflow you'll live in

```
# Compute an SLO from Prometheus (doc 11)
# Availability SLI over the last 30d:
rate(http_requests_total[30d] offset 0)  # good
sum(rate(http_requests_total[30d]))        # all
# in a dashboard: ratio + an error-budget-gauge panel

# MWMR alert (Prometheus rules):
# fast 1h burn:
  ( 1 - (rate(http_requests_total{job="outline",code=~"2..|3.."}[1h]) / rate(http_requests_total{job="outline"}[1h])) )
  > ( 1 - 0.999 ) * 14

# The *error-budget gauge* — "how much budget is left this month":
# budget_total_monthly = (1 - SLO) * seconds_in_30d * total_rate
#   = 0.001 * 2_592_000 * rate(...)   →  units: requests
# budget_spent = the integral of bad requests since month start
error_budget_remaining =
  (0.001 * 2592000 * sum(rate(http_requests_total{job="outline"}[1h])))
  - sum(increase(http_requests_total{job="outline",code=~"4..|5.."}[30d]))
# "hours until out" = error_budget_remaining / current_burn_rate
time_to_budget_exhaustion_hours =
  error_budget_remaining
  / (sum(rate(http_requests_total{job="outline",code=~"4..|5.."}[1h])) * 3600)
```

> **The L6 habit — put the *error budget gauge* on the dashboard.** Not "uptime %," but **"budget remaining this month / hours until we're out."** That one panel tells you the *posture*: green (plenty of budget, ship fast) vs. red (budget spent, freeze features, fix reliability). It's the SRE operating loop made visible. The `time_to_budget_exhaustion_hours` expression above is the "hours until out" panel; **alert when it drops below, say, 48h** — that's the "you're about to spend the whole month's budget" warning that fires *before* you're out.

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| SLI count | 3 (availability, latency, auth) — few, user-facing, defendable |
| SLO level | 99.9–99.5%, *affordable and measurable*, not a vanity number |
| Error budget | The number that gates change-speed; regenerate when spent |
| Burn-rate alerting | MWMR: 1h@14x (page) + 6h@1x (ticket); *both* windows |
| SEV mapping | By SLO burn, not feeling: 50x = SEV-2, ≥100x = SEV-1 |
| First goal in an incident | **Stabilize** (mitigate), *then* diagnose the preserved state |
| Postmortem test | "Did it make the class of failure structurally impossible?" |

---

## Failure modes you must deliberately cause

1. **Breach an SLO on purpose** (break `outline` login) → watch the MWMR alert fire, the error-budget gauge drop, and the SEV classify *by the numbers.*
2. **Run a rollback under incident pressure** (doc 04) → practice "mitigate first, no diagnosis required."
3. **Write a postmortem with zero action items** → feel how it *reproduces* the next incident; then close items and watch the failure not recur.
4. **Slow leak** (a config that costs 0.01% more errors every hour) → verify the 6h@1x window catches it while the 1h window stays quiet.
5. **Two incidents at once** (a SEV-1 + a SEV-3) → practice the IC *separating the hats* and keeping the room from going under the *coordination* load, not just the technical load.
6. **Silently change the SLO target** (99.9% → 99.5% in the alert config) → every burn-rate formula downstream silently changes: 50x burn now means 25% errors, not 5%. **Add a guard:** the SLO target lives in a *versioned, reviewed* source (a values file / a config repo), not free-text in an alerting snippet. Treat a target change like a code change — it needs review and a note that *the burn math moved.* This is a real failure: a "we relaxed the SLO" that quietly makes all alerts fire later and you *never notice* until a real 5% error day pages you at 14x instead of 50x.

---

## The L5/L6 lens: what panels probe to *refute* you

Not "what I'd say" — **what a hostile panel will ask to expose that you're reciting**, and the concrete number / artifact that *stops* the refute.

| Panel probe | The refute they're looking for | The concrete artifact that *stops* it |
|---|---|---|
| "What's your SLO?" | "You picked a vanity number." | "Availability 99.9%/30d, p99<500ms for 99%, auth 99.9%. Here's my *computed* budget: 0.001 × 2,592,000 s = 43 min of downtime allowed. I picked 99.9, not 99.999, because that's what I can *afford and measure* — five nines needs ~5.26 min *per year*, which a 3-node homelab can't defend." |
| "How do you alert?" | "You can't derive the burn rate." | "MWMR: 1h@14x pages, 6h@1x tickets. Burn = `actual_error_rate / (1 - SLO)`. On a 99.9 SLO, 30% errors = 300× burn. Here's the 1h formula and the *two-window worked example* (outage vs. slow bleed give different answers)." |
| "What do you do first in an incident?" | "You'd diagnose before stabilizing." | "Stabilize: mitigate without a diagnosis, preserve the failing state, *then* root-cause the repro. I've done the rollback-under-pressure drill (drill #2)." |
| "How do you stop this class of failure?" | "Your postmortem has no closed items." | "Blameless → every action item closes a *systemic* gap. The L6 test: 'did it make the failure structurally impossible?' Here's my postmortem template that *forces* a closed-item check before it's filed." |
| "How does reliability gate velocity?" | "You don't know the budget is the throttle." | "Error budget: green = ship fast, red = freeze features, spend capacity on reliability until it regenerates. I have the `error_budget_remaining` + `time_to_budget_exhaustion_hours` panels; alert at <48h to out." |
| "What if the SLO target changes?" | "Your burn math is fragile." | "The target lives in a versioned source, not free-text; a change is a reviewed code change with a note that the burn math moved. Drill #6 exercises the silent-change failure." |

> **The meta-skill, applied to reliability:** bring your *own* computed budget (43 min), your *own* burn-rate formula, and your *own* two-window example to the interview — not Google's slide. The panel can always ask "derive it for *your* SLO" — the one who's only reciting fails that.

---

## Exit criteria

- [ ] 3 user-facing SLIs with SLOs you can *defend and afford*
- [ ] Error-budget gauge on a dashboard (green = ship, red = freeze)
- [ ] MWMR alerts wired in Prometheus/Alertmanager (doc 11), firing on a deliberate breach
- [ ] SEV taxonomy mapped to SLO burn, not feeling
- [ ] One deliberate incident run end-to-end: detect → mitigate → postmortem with *closed* items
- [ ] A postmortem template that *forces* a "did it make the failure structurally impossible?" check

Next: `21-api-grpc-design` — the service-boundary skill Google's L6 is *famous* for.
