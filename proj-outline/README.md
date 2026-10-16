# proj-outline

> Own the entire platform. From bare metal to production-grade observability.

This project documents the complete platform journey using **Outline** (open-source team knowledge base by Gitlab 256-research) as the application payload. You deploy the app, but the real product is the **platform underneath it** — the thing that makes the app survive node failures, scale cleanly, and give you visibility into what's actually happening.

---

## Why Outline?

Outline is a self-hosted alternative to Notion, built by the team at GitLab 256-research. It forces every platform layer you want to learn:

| Layer | What Outline requires |
|---|---|
| Postgres | Primary data store — no SQLite, no managed service |
| Redis | Session store + job queue |
| S3-compatible storage | Attachment and file uploads |
| OIDC / JWT | User authentication via external identity provider |
| Background workers | Search indexing, Slack sync, email notifications |
| Multi-tier deployment | API server + worker processes |
| TypeScript monorepo | Real CI — lint, test, build, push |
| Prometheus metrics | Built-in endpoint (`/metrics`) |
| Production traffic | Meaningful dashboards, log volumes, resource pressure |

## Folder structure

```
proj-outline/
├── 00-learning-path          ← The arc: what to learn, in what order, and why
├── 01-terraform-infra        ← Terraform: Proxmox nodes, cluster bootstrap, cloud add-ons
├── 02-kubernetes-core       ← Kubernetes internals: API, etcd, control plane, networking
├── 03-helm-packaging        ← Helm: charts, values, templating, release management
├── 04-jenkins-cicd          ← Jenkins: JCasC, CI pipeline, CD pipeline, agents, webhooks
├── 05-artifact-repository   ← Harbor: registry, image tagging, Trivy scanning, replication
├── 06-postgres-stateful     ← CloudNativePG: operator, StatefulSet, PVC, connection pooling
├── 07-redis-queue           ← Redis: Sentinel/Cluster, persistence, memory management
├── 08-object-storage        ← MinIO: S3-compatible, tenant isolation, bucket policies
├── 09-oidc-auth-jwt         ← Keycloak / Authentik + Outline OIDC + JWT internals
├── 10-outline-app           ← Outline: architecture, deployment topology, env vars
├── 11-observability-metrics ← kube-prometheus-stack: Prometheus, Grafana, alerting rules
├── 12-logging-logs          ← Loki + Promtail (or ELK): log aggregation, retention, parsing
├── 13-node-health           ← node-exporter, node-problem-detector, kubelet, NTP drift
├── 14-security-hardening    ← RBAC, NetworkPolicies, PodSecurityStandards, secrets mgmt
├── 15-backup-dr             ← Postgres backup, Velero, snapshot strategies, RTO/RPO
└── 16-operations-runbook    ← Day-2 ops: rollbacks, scaling, debug sessions, on-call
```

## How to use this

Each folder is a self-contained learning unit:

1. **Read the README** — it teaches the concept first, then gets into the specifics of why it matters for this project.
2. **Follow the sequence** — folders are ordered by dependency. Don't skip `06-postgres-stateful` before `10-outline-app`.
3. **Build incrementally** — each milestone produces a working system. Don't move on until the previous one is stable.

## Milestone map

```
Week 1-2  │  Terraform: infra provisioning
Week 2-3  │  Kubernetes: control plane + networking
Week 3-4  │  Helm: packaging the app
Week 4-5  │  Postgres + Redis + MinIO: stateful foundations
Week 5-6  │  Jenkins: CI pipeline
Week 6-7  │  Harbor: artifact management
Week 7-8  │  CD pipeline: CI → image → deploy
Week 8-9  │  Keycloak: identity + JWT
Week 9-10 │  Observability: Prometheus + Grafana dashboards
Week 10-11│  Logging: Loki / ELK stack
Week 11-12│  Node health + Security hardening
Week 12-13│  Backup, DR, runbooks
```

## The senior engineer's mental model

As you work through each layer, ask yourself:

- **What breaks here, and how do I know it's broken?**
- **What happens when I roll this back?**
- **What's the blast radius of a misconfiguration?**
- **What would an on-call engineer need at 3am?**

The goal isn't to configure things — it's to build the intuition that lets you reason about systems you've never seen before.
