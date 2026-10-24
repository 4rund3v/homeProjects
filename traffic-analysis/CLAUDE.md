# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project intent

Docs-first learning scaffold for enterprise SRE/observability topics: latency percentiles (p50/p95/p99), L4 vs L7 load balancing, database latency, and related senior-engineer operational knowledge. No application code is the deliverable — the user builds and measures, Claude writes the teaching docs, labs, and worked examples.

## The observable system (what the user will actually deploy)

A Kubernetes cluster (kind or k3s) running a small e-commerce-ish stack, chosen to exercise every topic in the repo:

- **Ingress (L7)**: NGINX Ingress Controller in front, exposing an HTTP API. This is the L7 load balancer the user will tune and observe.
- **Application**: a tiny Go service (a single pod + HPA is enough) that serves `/api/products` and `/api/orders`, each doing one Postgres query. Application is a black box for the user — it exists to produce traffic and latency, not to be studied.
- **Database**: PostgreSQL with `pg_stat_statements` enabled, running on a PVC. PVC lets the user test disk latency, I/O, and node-anti-affinity.
- **Load layer**: an L4 load balancer in front of the cluster (a `MetalLB` VIP, or the cloud LB if running on GCP/AWS) — the user compares it to the NGINX L7 layer.
- **Observability**: Prometheus + Grafana + Alertmanager installed by Helm. A `ServiceMonitor` scrapes the app, NGINX (`nginx_ingress_controller_request_duration_seconds`), postgres-exporter, and node-exporter.
- **Artifact repo**: a local OCI registry (`registry:2` or `distribution/distribution`) in the cluster or on the host. The user builds the app image, pushes to the registry, and deploys from there. This exercises the release pipeline and version pinning.

Topology (single diagram, repeated in every topic doc):

```
  client
     |
     |  (L4) — MetalLB VIP / cloud LB, TCP-level, round-robin
     v
  k8s nodes
     |
     |  (L7) — NGINX ingress, HTTP-aware, path-based routing, TLS
     v
  app pods  ──> postgres pod ──> PVC
```

## Working style

- Completion is not the goal; understanding is. Each topic ends with a hands-on measurement exercise the user runs themselves.
- Prefer concrete worked examples (real numbers, real `kubectl`/`promtool`/`sysstat`/`ab`/`k6` output shapes) over abstract definitions.
- Do not write production-quality code in this repo. Snippets are illustrative.
- One topic per directory. Cross-link related topics rather than duplicating content.

## Layout

- `project/` — the system: architecture, how to deploy it, what to observe first. Start here.
- `latency-percentiles/` — p50/p95/p99/p999, histogram vs summary, sampling bias, SLOs, `histogram_quantile`.
- `load-balancing/` — OSI layer map (`06-osi-layers`: why only L4/L7 have LBs, L5/L6 folded into L7), L4 (TCP, LVS, iptables, MetalLB) vs L7 (HTTP, nginx, Envoy, service mesh), health checks, session affinity, connection drain.
- `database-latency/` — connection pool metrics, query latency percentiles, replication lag, lock waits, `pg_stat_statements` interpretation, slow-query thresholds.
- `observability/` — metrics vs logs vs traces, cardinality, RED/USE, alerting on SLOs, `histogram_quantile` math.
- `capacity/` — load testing methodology, Little's law, queueing intuition, saturation curves.

Each topic directory follows the same shape:

- `00-overview.md` — why the topic matters in an enterprise service, one-paragraph framing.
- `NN-*.md` — numbered deep-dive docs, one concept each.
- `labs/` — measurement exercises with exact commands, expected output shapes, and "what to look for" questions.
- `examples/` — real-shaped config snippets, dashboards, alert rules (illustrative, not prod).

`project/` follows the same shape but starts from `00-architecture.md` and ends in `labs/` with the deploy-and-observe labs.

## Writing rules for Claude in this repo

- Match the user's stated intent: teach, not build. Every doc says what to measure, what the number means, and what a "bad" number looks like.
- Cite metric names exactly as they appear in Prometheus (e.g. `http_request_duration_seconds_bucket`, `nginx_ingress_controller_request_duration_seconds`, `pg_stat_statements_mean_exec_time`), not invented variants.
- Distinguish L4/L7 clearly; the user's initial request said "L5" — treat as L7 (application-layer) unless corrected.
- Numbered topics use `NN-` prefix (01-, 02-, ...) so reordering is a rename.
- Labs are checklists: prerequisites, commands, expected output, follow-up questions. Never a wall of prose.
- Every doc in every topic links back to the corresponding part of `project/` so the user always knows *where in the running system* the concept lives.

## Anti-goals

- No `Makefile`, no CI, no test suite. This is not a code project.
- No scaffolding of a monitoring stack here (Prometheus/Grafana setup lives in `project/labs/` as a lab, not as tooling of this repo).
- Do not write the application code for the user; the app is intentionally minimal and provided as a reference in `project/examples/`.
