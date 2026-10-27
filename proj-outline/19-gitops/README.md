# 19 — GitOps: The L6 Delivery Pattern

**Folder:** `19-gitops/`

---

## Teach first: what GitOps is, and how it differs from the Jenkins CD in doc 04

You already built a Jenkins CD that *pushes* to the cluster (`helm upgrade` triggered by a pipeline, doc 04). GitOps **inverts the control flow**: instead of your pipeline pushing state *into* the cluster, a Git repo is the *declared* state and an in-cluster agent *pulls* and converges the cluster toward it.

```
Jenkins CD (push):     pipeline → helm upgrade → cluster changes
GitOps     (pull):     you commit to Git → ArgoCD/Flux watches Git → applies the diff to the cluster
```

The core property: **Git is the source of truth; the cluster is a *projection* of Git.** If reality drifts from Git, the agent *reconciles* it back. This is a reconciliation loop (the doc-02 pattern) applied to *your applications* instead of to k8s primitives.

> **The L5→L6 shift in one line:** pushing deploys (Jenkins) means "the pipeline is the actor." GitOps means "the system continuously *converges to the desired state* declared in Git, and Git is the only way to change it." The pipeline stops *being* the deployer and becomes *just one of many Git authors* (it can update an image tag in the repo, and the agent handles the rest).

---

## The two tools, and why you'll likely run one

| | **Argo CD** | **Flux** |
|---|---|---|
| Shape | UI-first + GitOps operator | Git-native, kubectl-style, no UI (pairs with k9s) |
| Git→cluster | watches Git, applies via its own controllers | same, via `git-repositories` / Kustomize controllers |
| Progressive delivery | Native (Argo Rollouts) | External (Flagger) |
| Learning surface | Rich: apps, sync windows, out-of-sync detection | Light: everything is a Git object |

> **What "out-of-sync detection" actually does (the mechanism, not the name):** Argo CD renders the *desired* manifest (from the Git ref) and *compares it field-by-field* against the *live* object in the API. Any field that differs — the image tag, a ConfigMap key, a replica count — shows up in the **`OutOfSync`** condition on the Application object, with a *diff* you can read:
> ```
>   *deployment outline-server:
>       image: "harbor.lab.example/outline:abc123"  →  "harbor.lab.example/outline:def456"
>       replicaCount: 3  →  2
> ```
> **This diff is the GitOps version of `helm diff` / `terraform plan`.** If you can't produce that diff on demand, you're not actually using GitOps — you're doing "apply-and-pray." Practice the drill: *intentionally* `kubectl set image` in the cluster, then run `kubectl argocd application diff outline` — the diff should show your change and the next sync should *revert it*. If it doesn't revert, GitOps isn't *managing* that object; it's just watching.

> **Flagger's "analysis step" (the Flux-side progressive delivery)** — *what a canary gate actually does, not what the name suggests:* Flagger's `Rollout` controller (or the Flux `Progressive Delivery` CRD) has an **analysis step** that runs on an *interval* (e.g., 60s) between traffic shifts. Each tick, the analysis step: (1) queries a metric source (Prometheus is the standard), (2) evaluates a threshold ("error rate < 1% in the last 5m" or "p99 < 500ms in the last 3m"), (3) either **advances** the traffic split (5% → 20% → 50% → 100%) or **rolls back** to the stable version if the metric breaches. **The gate is a closed loop, not a one-shot check** — that's the entire value. Without an analysis step, "canary" is just a slow rolling update.

> **Tradeoff — pick Argo CD to *learn GitOps + progressive delivery* in one tool** (Rollouts is the canary mechanic), **Flux if you want the minimal, "everything is a Git object" purity** and don't want a second cluster add-on UI. For this project, **Argo CD** is the better teacher: it makes the *declaration → reconcile → drift* loop visible in a UI you can point at, and its Rollouts feature teaches canary analysis (doc 22) concretely.

---

## App-of-Apps: the two-tier Git layout

The L6 pattern is **two tiers of Git, not one**:

```
Repo A: "gitops-apps"   ← the *apps* tier. Each Outline/KubeProm/Jenkins/Keycloak
                         deployment is an Argo CD "Application" object here.
                         Contains Helm values, kustomize overlays, image tags.
Repo B: "gitops-infra"  ← the *bootstrap* tier. Installs Argo CD *itself* and the
                         cluster add-ons (cert-manager, the ingress, monitoring).
```

- **App-of-Apps:** Argo CD, once installed, reads *Repo B* to install the "application of applications" — which is Repo A's Applications. Repo A then holds everything else.
- This separates **"what the cluster looks like when it first boots"** (B) from **"what's running on it day-to-day"** (A). A node loss or cluster rebuild plays B, then Argo self-heals to A.

> **The chicken-and-egg question, answered explicitly** — how does Repo B get applied on a fresh cluster if Argo CD itself lives in Repo B? It's **out-of-band**: on a brand-new cluster, you `kubectl apply` the Argo CD install *once* (Terraform's Helm provider, or a plain `helm install`, or `kubectl apply -f https://raw.githubusercontent.com/argoproj/argo-cd/.../install.yaml`). From that moment on, Argo CD *is* the thing that keeps Repo B converged, and **that initial install is the one out-of-band act in the whole system** — the same "bootstrap" concept from doc 01. Name it; it's the one thing you *can't* make self-healing without *some* external actor. If the bootstrap breaks (a bad commit to Repo B), the recovery path is the same out-of-band install — so keep the install manifest somewhere you can `kubectl apply` from a laptop without the cluster.

> **The boundary with Terraform (doc 01).** Where does GitOps end and Terraform begin? The clean split:
> - **Terraform** owns the things *outside* the cluster's API: the nodes/VMs, DNS, cloud resources, and *installing* the bootstrap add-ons.
> - **GitOps** owns *in-cluster* state: apps, Helm releases, Kustomize overlays.
> - **The handoff:** Terraform's Helm provider is the *bootstrap* path (doc 01's note about "Terraform for bootstrap, GitOps for steady state"). Don't fight it: Terraform brings Argo CD into existence; GitOps owns everything after that.

---

## Progressive delivery: the feature that earns the L6 bar

"Ship it and pray" is L4. **Progressive delivery** ships *incrementally and rolls back automatically on signal*. Argo Rollouts + Flagger give you:

| Strategy | How it works | Best for |
|---|---|---|
| **Rolling update** | Replaces pods one at a time; on failure, keep the old | default; what `helm upgrade` does |
| **Blue-green** | Two full sets; flip the Service to the green set; instant rollback | full-state swaps; lower risk than canary |
| **Canary** | Route 5% → 20% → 100% of traffic to the new version; auto-rollback on metric | the *most* powerful; requires a traffic signal + a *metric-based* analysis step |

**What "flip the Service to the green set" actually looks like.** A blue-green via Argo Rollouts creates *two* Deployments (`outline-server-blue` and `outline-server-green`), a `Service` (still named `outline-server`) that selects on a *stable label*, and a `Rollout` object whose `trafficRouting` block holds the actual flip:

```yaml
# The Rollout declares which set is "active" — that's the whole flip.
spec:
  strategy:
    blueGreen:
      activeService: outline-server-blue    # ← the flip: swap this
      previewService: outline-server-green
      promotionStrategy:
        auto:
          promotionLimitDuration: 1h        # auto-promote after 1h healthy
      abortScaleDownLimitSeconds: 900       # how long to keep the old set
```

The actual "flip" is a change to `activeService` (or an `analysis` gate that sets it). **Before the flip, the green set is *warm and idle* — you pre-verify it on a preview port before users ever hit it.** That's why blue-green beats rolling for full-state swaps: the *new* state is tested on 100% of a real pod before it takes 1% of real traffic.

> **The L6 detail — canaries are *metric-gated*, not just traffic-percentaged.** The real power is: "advance the canary to 20% *only if* error rate < 1% and p99 < 500ms in the last N minutes; else roll back." That turns a deploy into a *closed-loop experiment* (doc 22's chaos + doc 11's metrics). A canary with no metric analysis is just a slow rolling update — call it what it is.

### Sync waves

App-of-Apps lets you deploy **in dependency order**. Deploy the Postgres schema *before* the app that needs it:

```
Sync wave 0: database (CNPG), redis, minio
Sync wave 1: keycloak, ingress, cert-manager
Sync wave 2: outline (server + workers)
```

Each wave waits on the previous (readiness probes / a "wave complete" hook). This is how you make a multi-app deploy *ordered* instead of "everything at once, hope."

---

## Drift and "self-healing" — the property you must own

The whole point of pull-based GitOps is **the cluster converges to Git even when something pokes it out of place.** A `kubectl edit` in the cluster is *drift*; on the next sync window Argo detects out-of-sync and **reverts it** to the Git state.

> **Failure mode — drift becomes a fight.** If operators keep `kubectl edit`-ing (doc 02's "out-of-band state" smell), GitOps reverts them and they keep editing — a war. The L6 fix is *process*, not just tech: **the cluster is not the source of truth; make every change a Git commit, and have GitOps *enforce* that.** Pair it with doc 14's (read-only) admission / doc 16's change discipline.

> **Tradeoff — auto-heal vs. auto-suspend.** Fully automatic convergence is ideal but dangerous: a bug in your Git repo can make GitOps *aggressively destroy a working cluster* (reconcile to a broken state). Mature setups have **sync windows** (quiet hours where it *won't* apply), **health gates** (only advance if the last sync was healthy), and a **manual "suspend"** knob for emergencies. Self-healing that you can't stop is a foot-gun.

---

## The workflow you'll live in

```
# The human path: change is a PR to gitops-apps, agent applies it
git commit -m "bump outline image to <sha>"   # doc 04's Jenkins still *produces* the image
# Argo CD detects the Git change → creates an "out of sync" → applies → health-checks

kubectl get application -n argocd
kubectl argocd application diff outline            # what's about to be applied?
kubectl argocd application sync outline            # manual nudge (if auto-sync is suspended)
kubectl argocd application set outline ...         # emergency override (reverted by next sync — by design)
```

> **The L6 observation: Jenkins and GitOps *coexist*, they don't compete.** Jenkins (doc 04) *builds the image and pushes to Harbor.* GitOps *decides which tag runs where.* The Jenkins CD's "helm upgrade" step becomes "update the tag in `gitops-apps` and push" — and GitOps does the deploy. **The pipeline author is now a Git author; the deployer is now the cluster.** That reassignment is the entire L6 mental model of delivery.

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| Push vs. pull | Pull (GitOps) for steady-state apps; keep Jenkins for build + registry push |
| Argo vs. Flux | Argo to learn (UI + Rollouts); Flux for minimal purity |
| Git tiers | bootstrap repo (B) + apps repo (A); B installs B-infra + Argo, A is everything else |
| Order | Sync waves in dependency order (DB→identity→apps) |
| Progression | Rolling (default) → blue-green → *canary with metric analysis* (the L6 bar) |
| Drift | Cluster is a projection of Git; changes are commits; auto-revert is the contract |
| Safety | Sync windows, health gates, a manual suspend; *never* un-stoppable self-heal |

---

## Failure modes you must deliberately cause

1. **`kubectl edit` a managed resource** → watch GitOps revert it on the next sync. (The drift contract in action.)
2. **Commit a broken value to `gitops-apps`** → the agent applies it, health check fails, (with a Rollout analysis step) it auto-rolls back. Without the analysis step, it's stuck broken until *you* commit the fix. Know which you have.
3. **Take down a node running Argo CD** → it's a Deployment; k8s reschedules it; verify it re-converges from Git *without* you touching the cluster.
4. **Suspend Argo and edit the cluster** → the edit *sticks* (no reversion). Now re-enable and watch it converge back. Feel why "self-heal you can't stop" is a foot-gun.
5. **Break the sync-wave order** (app deploys before its DB) → observe the crashloop; re-impose the wave ordering.
6. **Run a metric-gated canary** on Outline, then *inject latency* on the canary variant → confirm the analysis step *holds* it at 5% and rolls back. This is the doc-22 payoff.
7. **Revoke the Git token / take the Git remote down** → Argo CD can't *read* the desired state. Verify: (a) already-applied state keeps running (GitOps doesn't *run* anything live; it just converges), (b) *new* changes can't be pulled, (c) your drift-detection is now blind. This is the SPOF a panel will probe — Git remote + token are the "source of truth" and if *that's* down, the whole model degrades to "last known Git state."
8. **Test a sync window** — suspend auto-sync for 2 hours, make a Git change, and confirm it *holds* until the window closes (rather than applying immediately or never applying). This is the drill that proves the "quiet hours" knob actually works.

---

## The L5/L6 lens: what panels probe to *refute* you

Not "what I'd say" — **what a hostile panel will ask to expose that you're reciting**, and the concrete artifact that *stops* the refute.

| Panel probe | The refute they're looking for | The concrete artifact that *stops* it |
|---|---|---|
| "Push or pull?" | "You don't know *why* pull beats push." | "Reconciliation beats actuation: a push pipeline deploys once, then the cluster drifts forever. Git makes the *declared state* continuously enforceable — the cluster can't stay out of sync. *And* the artifact: I've `kubectl edit`ed a resource and watched Argo revert it on the next sync (drill #1). That's the concrete proof." |
| "Where does Terraform stop?" | "You can't state the boundary." | "Outside the cluster API — nodes, DNS, *and* the bootstrap add-ons. In-cluster, day-to-day, is a Git object. The handoff: Terraform's Helm provider brings Argo CD into existence (bootstrap, doc 01); GitOps owns everything after. No overlap; Terraform stops at the *install* of Argo." |
| "How do you deploy a breaking change?" | "You can't describe the gate." | "Sync waves in dependency order; the deploy is *gated on the previous wave's health*, and a canary advances *only* on a metric signal (error rate < 1% and p99 < 500ms in the last 5m). I have a *test canary with a metric gate* (drill #6) — here's the config: `analysis.step` polls Prometheus every 60s, holds at 5% while the metric is red, advances to 20% when green." |
| "What's the SPOF?" | "You think the cluster is the SPOF." | "The *Git remote + token* is the SPOF, not the cluster. If Git is down, the *declared* state is unreachable — applied state keeps running (GitOps doesn't run things live), but new changes and drift detection stop. Drill #7 exercises exactly this." |
| "Why does this matter more than a Helm push?" | "You're selling GitOps as a tool." | "The value is *the property*, not the tool: a continuously-enforceable declared state. If I had to pick Flux over Argo CD, or even hand-rolled `kubectl apply` in a CronJob, I'd take the property over the tool. Argo CD is just the one with a UI I can point at and a native Rollouts for canaries." |

> **The meta-skill, applied to delivery:** for every delivery choice — Argo vs. Flux, sync waves, the canary threshold — you should be able to state the **four-part structure** (decision / constraint / rejected alternative / revisit condition) *without notes*, with *your own* drill logs, not a slideware example.

---

## Exit criteria

- [ ] Argo CD (or Flux) installed via the bootstrap repo; it self-heals from Git on node loss
- [ ] Two-tier Git: bootstrap repo + apps repo; the handoff is clean and you can *explain* where each owns
- [ ] Outline + every add-on is an in-cluster Git application (no out-of-band `kubectl edit` you have to re-do)
- [ ] Sync waves deployed in dependency order; a wave-gate observed holding until the previous wave is healthy
- [ ] A **metric-gated canary** on Outline that rolls back on an injected bad signal
- [ ] Drift contract understood: out-of-band edits revert; you've deliberately run it
- [ ] You can state, without notes, the Jenkins↔GitOps↔Terraform boundary and *why pull beats push*

Next: `20-incident-slo` — the reliability discipline GitOps hands you on a chain.
