# 00 — The Learning Path

Before touching a single tool, understand **what you're actually building** and **in what order it makes sense to build it**. This document is the map. Everything else in `proj-outline/` fills in a region of it.

---

## The one-sentence version

You are going to build a **production-grade internal platform** on your own hardware, where a real application (Outline) runs on a Kubernetes cluster that you provision with Terraform, package with Helm, build and ship with Jenkins, store artifacts in Harbor, secure with least-privilege RBAC and OIDC, and observe with Prometheus, Grafana, and a log pipeline.

The point is not Outline. The point is the platform. Outline is the thing that puts realistic load and realistic failure modes on your platform so the lessons stick.

---

## Teach first: the layers, from the bottom up

Think of the whole thing as a stack. Each layer depends on the one below it. When something breaks, you debug *upward* from the bottom — because a "Grafana is down" symptom might actually be "the node ran out of inodes six hours ago."

```
┌─────────────────────────────────────────────────────────┐
│  16. Operations       runbooks, on-call, incident process│
├─────────────────────────────────────────────────────────┤
│  15. Backup & DR      RPO/RTO, restore drills, snapshots │
├─────────────────────────────────────────────────────────┤
│  14. Security         RBAC, NetworkPolicy, secrets, PSS  │
├─────────────────────────────────────────────────────────┤
│  13. Node health      exporters, NPD, kernel, disk, NTP  │
├─────────────────────────────────────────────────────────┤
│  11/12. Observability Prometheus, Grafana, Loki/ELK      │
├─────────────────────────────────────────────────────────┤
│  10. Application      Outline (API + workers)            │
├─────────────────────────────────────────────────────────┤
│  09. Identity         Keycloak, OIDC, JWT                │
├─────────────────────────────────────────────────────────┤
│  06/07/08. Stateful   Postgres, Redis, MinIO             │
├─────────────────────────────────────────────────────────┤
│  04/05. Delivery      Jenkins, Harbor                    │
├─────────────────────────────────────────────────────────┤
│  03. Packaging        Helm                               │
├─────────────────────────────────────────────────────────┤
│  02. Runtime          Kubernetes                         │
├─────────────────────────────────────────────────────────┤
│  01. Foundation       Terraform, nodes, networking       │
└─────────────────────────────────────────────────────────┘
```

**Read it bottom-up to understand dependencies. Read it top-down to debug.**

---

## Why this order?

The order is not arbitrary. It follows the dependency graph:

1. **You can't run Kubernetes without nodes.** → Terraform first.
2. **You can't package a Helm chart against an API you don't understand.** → Kubernetes before Helm.
3. **You can't deploy stateful apps safely without understanding PVCs and StatefulSets.** → Kubernetes core before Postgres/Redis.
4. **You can't build a CI/CD pipeline for an app you haven't deployed manually once.** → Deploy by hand first, then automate.
5. **You can't debug a system you can't see.** → Observability comes before you go deeper into the app.
6. **You can't secure a system you don't understand the topology of.** → Security hardening last, once you know what flows where.

---

## The "deploy it by hand first" principle

This is the single most important habit in the entire project.

> **Never automate something you haven't done manually at least once.**

When you `helm install` something blind, and it fails, you have two unknowns: *is the thing broken, or is my automation broken?* Doing it by hand first collapses that into one unknown.

So for **every** component:

1. **Manual** — install it with `kubectl apply` or `helm install` by hand. Understand every resource.
2. **Reproducible** — capture it as code (Helm values, Terraform, a manifest).
3. **Automated** — wire it into Jenkins so a pipeline does it.

You will build each component three times. That is intentional. The third time is where the intuition forms.

---

## What "really comfortable" actually means

You said you want to be *really comfortable with the entire process*. Here's the concrete bar — the things a senior engineer can do that a junior cannot:

| Junior | Senior |
|---|---|
| Can follow a tutorial to deploy X | Can explain *why* X is deployed that way, and what it'd cost to change |
| Debugs by reading error messages | Debugs by reasoning about *which layer* the failure is in |
| Knows a tool's flags | Knows the tool's failure modes and operational limits |
| Copies a Helm chart and tweaks it | Knows what the values control and what happens at the extremes |
| Fixes the symptom | Fixes the root cause, then removes the class of failure |
| Adds dashboards that look nice | Adds dashboards that answer a specific question an on-call engineer will ask |
| Thinks in components | Thinks in *data flows* and *failure domains* |

Every doc in this project is written to push you toward the right-hand column.

---

## Thresholds, tradeoffs, and the "why"

Throughout these docs you'll see callouts like:

> **Tradeoff** — the choice, and what you give up either way.
>
> **Threshold** — a concrete number where behavior changes (e.g. "Postgres autovacuum degrades past ~20% bloat").
>
> **Failure mode** — what breaks and how you'd notice.
>
> **Senior lens** — the thing an experienced engineer checks that a beginner doesn't.

These are the parts you cannot get from a tool's documentation. A tool's docs tell you what a knob does. A senior engineer knows *when turning it costs you more than it gains*.

---

## The failure-first mindset

A platform you haven't broken is a platform you don't understand.

For every component, deliberately cause the failure it's designed to survive:

- Kill the Postgres primary → does failover work? Did the app reconnect?
- Drain a node → do pods reschedule? Does anything get stuck on a PVC?
- Fill the disk → does the kubelet start evicting? Do your alerts fire *before* it's fatal?
- Expire a JWT → does the app reject it cleanly or crash?
- Delete a namespace → is your backup actually restorable?

**The goal is not a system that never fails. It's a system whose failures you've already seen, predicted, and built a response for.**

---

## Milestones (dependency-ordered)

Each milestone should end with a **working, observable system**, not a folder of YAML.

### Foundation
- **M1 — Infra**: Terraform provisions nodes; a Kubernetes cluster exists; you can `kubectl get nodes`.
- **M2 — Core runtime**: ingress-nginx + cert-manager installed; you can reach a `hello-world` over TLS.

### State
- **M3 — Stateful foundations**: CloudNativePG Postgres, Redis, MinIO all running with PVCs; you can `psql` in and `mc` a bucket.
- **M4 — Identity**: Keycloak running; a test client can get a JWT via OIDC.

### Delivery
- **M5 — Registry**: Harbor running; you can push and pull an image; Trivy scans it.
- **M6 — CI**: Jenkins builds Outline from source and pushes to Harbor.
- **M7 — CD**: Jenkins deploys Outline to the cluster via Helm, gated on approval.

### Application
- **M8 — Outline live**: You log in via Keycloak OIDC and create a document.
- **M9 — Workers**: Background jobs (search indexing, email) process correctly.

### Visibility
- **M10 — Metrics**: Prometheus scrapes everything; you've authored Grafana dashboards.
- **M11 — Logs**: Loki/ELK aggregates logs; you can trace a request across services.
- **M12 — Node health**: Alerts fire on disk/memory/kernel pressure.

### Resilience
- **M13 — Security**: RBAC and NetworkPolicies locked down; no cluster-admin in workloads.
- **M14 — Backup/DR**: A full restore drill from backup succeeds.
- **M15 — Runbook**: You can hand the platform to another engineer and they can operate it.

---

## How to know you're done

You are done when you can:

1. **Destroy the entire cluster** and rebuild it from Git in under an hour, unattended.
2. **Kill any single component** and explain the blast radius without looking.
3. **Get paged** by your own alert and resolve it using only your dashboards and runbook.
4. **Explain the tradeoff** of every major decision — why CloudNativePG and not a plain chart, why Loki and not ELK, why this ingress and not that one.

That's the bar. Now start at `01-terraform-infra`.
