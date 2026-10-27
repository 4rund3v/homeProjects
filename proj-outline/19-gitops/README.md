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

---

## The L5/L6 lens: what this signals

| Probe | L6 answer |
|---|---|
| "Push or pull?" | "Pull. Git is source of truth; the cluster converges to it. Jenkins builds + pushes images; GitOps *decides where a tag runs*. The pipeline is a Git author, not the deployer." |
| "Where does Terraform stop?" | "Outside the cluster API — nodes, DNS, and the *bootstrap* of add-ons. Everything in-cluster, day-to-day, is a Git object. Bootstrap repo installs the apps repo's machinery; I keep the handoff clean, not overlapping." |
| "How do you deploy a breaking change?" | "Sync waves in dependency order; the deploy is *gated on the previous wave's health*, and a canary advances *only on a metric signal*. If the signal's red, it rolls back before humans notice." |
| "What's the failure mode?" | "GitOps is a new SPOF that *aggressively* converges — a bad commit can destroy a working cluster. I gate with health checks, sync windows, and a manual suspend I can actually use." |
| "Why does this matter more than a Helm push?" | "Because *reconciliation* beats *actuation*. A push pipeline deploys once and the cluster can drift forever. GitOps makes the *declared state* continuously enforceable — the cluster can't stay out of sync. That's the reliability property." |

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
