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
*Get *buy-in* **before** building, across teams, by arguing the tradeoffs.* A complete 1-2 page RFC (not just the section headers) is the artifact a panel will actually read — here's a filled-in one you can pattern-match:

```
# RFC-0043: Replace the Jenkins-push CD step with GitOps (Argo CD)

Status: Proposed   Owner: <you>   Affected: Delivery, App, Data, Security

## Problem
Our CD is push: a Jenkins job runs `helm upgrade` into the cluster. That
means (a) the cluster's live state can drift from anything in Git and
nobody notices until a deploy; (b) the deployer is the *pipeline*, so a
mid-deploy failure leaves a half-applied state the pipeline doesn't
reconcile; (c) there's no *converge-to-desired* — a `kubectl edit`
persists with no guardrail.

## Proposal
Adopt Argo CD as the in-cluster reconciler. Apps live in `gitops-apps`;
Argo watches that repo and converges the cluster to it. The Jenkins
pipeline keeps *building and pushing images* to Harbor; its "deploy"
step changes from `helm upgrade` to "update the image tag in
gitops-apps and push" — Argo does the deploy.

## Tradeoffs (vs. keeping Jenkins push)
+ Reconciliation: the cluster *cannot* stay out of sync; drift reverts.
+ The pipeline stops being the deployer — it's just a Git author, so any
  other Git author (a human, another bot) can deploy.
− Argo CD is a new control-plane component to run and secure.
− A bad commit can now *aggressively* converge a working cluster to a
  broken state → we gate with health checks + a manual suspend.
Rejected: keeping Jenkins push (the above drift + SPOF-of-the-pipeline
problems); a bare CronJob `kubectl apply` (converges but has no
progressive delivery / health gates / out-of-sync UX).

## Migration
1. Install Argo CD in the bootstrap repo (doc 19).  2. Move Outline +
   add-ons into gitops-apps as Applications.  3. Cut Jenkins' CD step
   to a tag-bump commit.  4. Run 2 weeks with both watching; verify
   zero out-of-band edits before deleting the push path.

## Open questions
- Does the mesh (doc 18) change which namespaces Argo can manage?
- What's the Suspend/runbook path for a bad commit?

## Adoption
First: `outline`. Default becomes: every new app ships as a gitops
Application (not a Jenkins deploy). Leverage: N = every future
deployment + every drift event after cutover.
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
>
> **How to actually count N (the method, not the vibe):** "N future services inherit it" is a *placeholder* unless you can *list them*. Concretely: N = the number of **repos/services that import your default** or **that your decision makes cheaper**. You can enumerate: `git grep` for the template/chart your new services consume; count the teams whose deploy path your GitOps change touched; count the PRs that no longer need a hand-rolled security review because the default is in place. **If N resolves to 1, you've described an L5 one-off with L6 language — and a panel will catch the inflation. If you can't produce the list, drop the "N services" framing and describe the *single* real impact you actually had.**

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
6. **The *Over*-claim** — the mirror of the Vanity-metric trap: an L6 candidate who frames an N=1 outcome with "N services" language. The counter-example a panel loves to hand you: *"You said the GitOps move 'improved every future deploy,' but only the outline app actually moved onto it."* The move: **re-state the claim at the N you can actually enumerate**, and say so. Inflating is more disqualifying than under-claiming — a panel can't argue with a claim that's *credibly sized.*

---

## The L5/L6 lens: what a panel probes to *refute* you

Not "what I'd say" — **what a hostile panel will ask to expose that the leverage is inflated**, and the concrete artifact that *stops* the refute.

| Panel probe | The refute they're looking for | The concrete artifact that *stops* it |
|---|---|---|
| "What did you *actually* build?" | "You're claiming the platform, not your slice." | The doc-01–22 build *with the dependency chain you personally owned end-to-end* — craft evidence, not a résumé bullet. |
| "Where's the *L6* in it?" | "It's L5 craft, packaged." | Leverage claims *with N listed*: "the GitOps default now covers [named services]; the secure-default template was inherited by [named teams]; the contract-test gate is in [named CI]." Not "N future services." |
| "What's your hardest decision?" | "You recite, not reason." | One decision narrated in the **four-part structure** off the top of your head — *including the one you'd redo.* |
| "What did you improve in *others'* work?" | "You improved your own." | A *named* downstream: "team X's onboarding is [concrete delta] cheaper because of the runbook/ADR; team Y's deploys no longer need a hand security review because the default is in place." |
| "What's your biggest risk?" | "You'll say 'the cluster'." | "Me being the *single brain* (an L5 bottleneck). The L6 fix is self-service + runbook + ADRs so *anyone* operates it — here's the cold-start drill I ran (doc 16's exit)." |
| "Where's the *over*-claim in your own case?" | "You don't know when to hold back." | **The self-check you can articulate:** "Where I said 'N services' and N actually resolves to 1, I drop the multiplier and describe the single real impact. Credibly L6 on two things beats inflated-L6 on five." |

> **The meta-skill, applied to the promotion case:** every leverage line must survive **"can you *list* the N?"** If you can't produce the list, that line is L5 language wearing an L6 costume — and a panel's whole job is finding that costume. **The single most disqualifying move is claiming a multiplier you can't enumerate.**

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
