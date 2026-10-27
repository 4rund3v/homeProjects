# 23 — Technical Leadership, Impact, and the L5→L6 Shift

**Folder:** `23-leadership-impact/`

This is the meta-layer. Docs 00–22 are the *craft*; this is how the craft becomes **career** — the L6 promotion material. The single most important idea:

> **L5 is *individual* ownership. L6 is *systemic* impact — you don't just build a thing, you change how a *team or org* builds things, and you make others better.**

---

## Teach first: the L5 vs. L6 *difference*, precisely

| | **L5 (Senior)** | **L6 (Staff / L6 at Google's scale)** |
|---|---|---|
| Scope | A system or a team's work | A *domain*, multiple teams |
| Decisions | The *right* decision, *well-reasoned* | Decisions that *compound* — set up the next 5 projects well |
| Influence | Through your work | Through *other people's* work (and you're *measured* on that) |
| Failure | A bad decision in your system | A *class* of bad decisions, across systems |
| Communication | You can explain your work | You can get *others* to make good decisions |

> **The L6 signal is *scope + leverage*.** Not "I built a big thing" (that's L5), but **"I made it so N teams no longer make that mistake"** — the impact is *multiplicative* because it travels. This is why a staff engineer who ships *one* service is *less* impressive than one who changed how *ten* services get built. The project in this repo is the *proof* of the craft; **the leverage is the L6 part.**

---

## The L6 leverage moves, mapped to *this* project

You've built a whole platform in `proj-outline/`. Here's where *each* becomes an **L6 impact** rather than just a deliverable:

| What you built (docs) | L5 version | **L6 version (the leverage)** |
|---|---|---|
| Terraform + GitOps (01,19) | "I provisioned the cluster" | **I made every engineer *able to* self-service infra; `terraform plan` empty is a *team* health metric** |
| Helm + values (03) | "I packaged Outline" | **I wrote the *values-vs-configmap* rules and the *chart template* everyone else copies — a *standard*, not a chart** |
| SLOs + error budgets (20) | "I set up alerts" | **I made *velocity* a function of a *reliability budget*; the whole team now ships against a number, not a feeling** |
| Testing layers (22) | "I added tests" | **I made the *contract* the test, so 5 teams change services without breaking each other** |
| Security (14, 18) | "I locked down the cluster" | **I made the *default* secure (least-privilege SAs, mesh mTLS); the *team's* work is now safe by construction** |
| Backup/DR (15) | "I made backups" | **I made *recovery a *drilled, measured* RTO/RPO the whole platform is sized against** |
| Incident/SLO (20) | "I handled an incident" | **I made *blameless postmortems + closed action items* a team habit — the system *structurally* improves after every SEV** |

> **The pattern, named: *make the good thing the default.*** L5 makes *one* thing well. L6 makes *everyone else's default* better. **Every line in that table is "I turned *my* craft into *their* default."** That's the promotion narrative in one sentence.

---

## ADRs and RFCs: the *artifacts* of L6

The two documents that *are* the L6 practice (doc 17's ADR, extended):

### Architecture Decision Record (ADR)
*Record a decision and *why*, so the next person doesn't re-litigate it.* (Full template + the four-part structure in doc 17.)

### RFC / design doc
*Get *buy-in* **before** building, across teams, by arguing the tradeoffs.* An RFC is:
```
## RFC-0043: Replace Jenkins CD with GitOps for all app deploys
Problem, Proposal, Tradeoffs (vs. Jenkins), Migration, Open Questions,
Adoption plan (which team first, what the default becomes)
```

> **The L6 distinction: ADR = *after* the decision (record it). RFC = *before* (win agreement).** Both are **versioned, in Git, *readable by a stranger* without your help.** A system where the decisions live only in one person's head is a system that person owns alone — that's an L5 bottleneck. **The L6 move is making the *decision* portable: it survives in a doc, not in a brain.**

---

## Driving a cross-team project (the L6 *execution* skill)

An L6 owns outcomes that *no single team can deliver alone.* The Outline platform touches: infra (Terraform), delivery (Jenkins/GitOps), data (Postgres/Redis), identity (Keycloak), observability, security. **No one person built all of that; the L6 role is making it *cohere.***

The concrete moves:
1. **Define the *end-state* everyone agrees on** — not tasks, but *"in 2 months, any engineer can deploy Outline to a fresh cluster unattended, and recovery is a measured 1h RTO."* The shared end-state is what aligns *independent* teams.
2. **Set the *interfaces* between teams early** — the values-vs-configmap contract (03), the API contract (21), the service-identity model (18). **Interfaces are where teams fail to coordinate; design them *first*, in an RFC.**
3. **Make progress *visible*** — a dashboard of *system* health (SLOs, error budget, drift, backup age) that *everyone* looks at (20, 11). Shared visibility is what makes *independent* teams act like one.
4. **Protect the *defaults*** — when a new service lands, it *inherits* the secure defaults (least-privilege, mesh, SLO gate). The L6 isn't just the one-off; it's the *template the next 5 services get for free.*

> **Threshold — "leverage" is measurable.** The test of an L6: *"How many other engineers' work did your decision improve?"* If the answer is "one," it's L5. The GitOps move improved *every* future deploy. The contract-test move improved *every* service boundary. The secure-default move improved *every* new service. **Count the *downstream beneficiaries*, not the *lines you wrote.***

---

## Mentoring: the *second* L6 lever

You're measured on *others'* growth, not just your own. In a solo-homelab, the "others" are *future-you* and *anyone you hand it to:*

- **The docs *in this repo are your mentoring artifact.*** `values-vs-configmap.md` (03), the "failure modes you must deliberately cause" drills (every doc), and the "L5/L6 lens" sections *are* how you make the next engineer (or your 6-months-later self) competent without you present.
- **The L6 test of a doc: can a stranger operate the system from it *alone*?** That's the exit criterion in doc 16 ("another human/agent cold-starts and operates it"). **Documentation-as-leverage is a genuine L6 skill.**
- **Code review / onboarding.** A *good* L6 makes onboarding *cheaper* — the runbook (16), the postmortems (20), the ADRs (17) are the onboarding *path* for the next person.

---

## The promotion narrative (the artifact a panel actually reads)

The L5→L6 case is **three stories, each with a *leverage* claim:**

1. **Craft** — "I built the Outline platform end-to-end (docs 01–22): a real, HA, observable, secure, self-healing system. *(Proof I can do the craft at L5-level complexity.)*"
2. **Leverage** — "But the *L6* part: I turned the *decisions* into *defaults* — the GitOps standard (19), the values/contract rules (03, 21), the secure-by-construction mesh (18), the SLO-gated velocity loop (20), the drilled-DR posture (15). *N* future services inherit all of it. ***(This is the multiplicative impact.)*"
3. **Judgment** — "I made *compound* decisions under *constraints* and *can state the tradeoff, the constraint, the rejected alternative, and the revisit-condition for each* (the four-part structure, doc 17). *That's the reasoning an L6 is supposed to bring to a room.*"

> **The meta-skill — the four-part structure is *the* L6 verb.** *Decision / Constraint / Rejected alternative / Revisit condition.* Every non-obvious choice in this project, narrated in that shape, *is* the L6 promotion case. (Doc 17 has it; doc 23 makes it the *story.**)

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| L5 vs. L6 scope | L5 = one system; L6 = a *domain* / multiple teams |
| The L6 verb | **Make the good thing the *default*; count *downstream beneficiaries*** |
| ADR | After the decision — record it, make it portable |
| RFC | Before the decision — win *agreement* across teams |
| Project driving | Define a *shared end-state*, set *interfaces first*, make progress *visible*, protect *defaults* |
| Mentoring | This repo's docs *are* the mentoring artifact; the test: "can a stranger operate it alone?" |
| Promotion narrative | Craft + Leverage + Judgment, each with a *multiplicative* claim |

---

## Failure modes you must deliberately notice

1. **The *Bottleneck* pattern** — "only I know how to deploy X" → the L6 *failure* (you're an L5 with scope, not L6 *leverage*). Fix: the GitOps self-service + runbook (01,16,19) so *anyone* can.
2. **The *One-off* trap** — "I fixed the incident" (L5) vs. "I made the *class* of incident structurally impossible" (L6, doc 20's postmortem test). Which did you do?
3. **The *Vanity metric*** — "I wrote 2,000 tests" (L5) vs. "I made the *contract* the test, so 5 teams evolve a service without breaking it" (L6, doc 22). Count *leverage*, not volume.
4. **The *Decision trapped in a brain*** — a system whose reasoning "lives only in my head" is an L5 *risk*, not an L6 asset. Fix: the ADR/RFC (this doc + 17) makes it *portable*.
5. **The *Default that rots*** — "secure by construction" (14) only stays true if a *new* service *inherits* it. The L6 move is the *template*, not the one application.

---

## The L5/L6 lens: what this *whole repo* signals to a panel

| Probe | L5 answer | **L6 answer (the bar this repo is built for)** |
|---|---|---|
| "What did you build?" | "The Outline platform, docs 01–22." | "The platform, *and* I made its *decisions into the team's defaults* — GitOps, the contract/secure defaults, the SLO-gated loop, the drilled DR. *N* future services inherit all of it." |
| "What's the hardest call?" | "HA Postgres." | "Every *compound* choice, narrated as *decision/constraint/alternative/revisit-condition*. The four-part structure is how I'd bring it to a room." |
| "What made you *not* just do the one-off fix?" | (a pause) | "I made the *class* of failure structurally impossible — the postmortem test: did it *change the system*?" |
| "How did you *improve others*?" | "I wrote docs." | "The docs *are* the leverage: a stranger cold-starts the platform from them (doc 16's exit). I *reduced onboarding cost.*" |
| "What's your biggest risk?" | "The cluster goes down." | "*Me* being the bottleneck (single-brain system). The L6 fix: GitOps self-service + runbooks so *anyone* operates it — I made the *team* capable, not just the system." |

---

## Exit criteria (the *career* bar)

- [ ] You can state the L5→L6 *difference* (scope + leverage) and your *own* work against it
- [ ] **Three** artifacts in *portable* form: one RFC (cross-team agreement), 5+ ADRs (the four-part structure, doc 17), one *blameless postmortem* with **closed** items (doc 20)
- [ ] A *measured leverage* claim: "decision X improved the default for N services" — with N *named*
- [ ] The *promotion narrative*: Craft + Leverage + Judgment, each with a *multiplicative* (not additive) claim
- [ ] The *bottleneck self-check*: can a stranger operate the platform from these docs *alone*? (If not, that's your next doc.)

---

## The through-line, last time

The whole `proj-outline/` project is one argument:

> **I can build a real, production-shaped platform (the craft, 01–22), and I can turn every decision I made into a *default that makes everyone else's work better* (the leverage, 23). The craft proves I can do the work; the leverage proves I'm *worth the L6 scope* — because my impact *compounds* past my own system.**

That is the entire L5→L6 case. Every other doc in this repo is a *piece* of that argument.
