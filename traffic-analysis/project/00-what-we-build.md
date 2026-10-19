# 00 — What we are building, and what we will measure

## The goal

One observable system, in a Kubernetes cluster, that produces real traffic and real latency. Every topic in this repo attaches to a specific part of that system. You deploy it once; then each lab in each topic points at the same running thing and measures a different slice of it.

```
        ┌─────────────────────────────────────────────────────────┐
        │                    Kubernetes cluster                   │
        │                                                         │
 client │  ┌──────────┐     ┌──────────────────┐                  │
   ───► │  │ MetalLB  │ ──► │  NGINX Ingress   │  (L7, HTTP)      │
   L4   │  │  (VIP)   │     │    controller    │                  │
   LB   │  └──────────┘     └───────┬──────────┘                  │
        │                           │                              │
        │                           ▼                              │
        │                  ┌──────────────────┐                    │
        │                  │  app pods (Go)   │                    │
        │                  │  /api/products    │                    │
        │                  │  /api/orders      │                    │
        │                  └───────┬──────────┘                    │
        │                            │                              │
        │                            ▼                              │
        │                  ┌──────────────────┐   ┌────────────┐   │
        │                  │  postgres pod    │──►│  PVC (SSD) │   │
        │                  │  pg_stat_stmts   │   └────────────┘   │
        │                  └──────────────────┘                    │
        │                                                         │
        │  Observability (Helm-installed):                        │
        │    prometheus ──► grafana ──► alertmanager              │
        │    node-exporter, postgres-exporter, NGINX annotations  │
        │                                                         │
        │  Artifact repo: local OCI registry in cluster           │
        │    (registry:2 or distribution/distribution)           │
        └─────────────────────────────────────────────────────────┘
```

## Why this particular stack

| Piece | What it teaches |
|---|---|
| **MetalLB** | L4 load balancing: TCP-level, round-robin, no app awareness. You will watch connections land unevenly and see how health checks decide "up/down". |
| **NGINX Ingress** | L7 load balancing: HTTP-aware, path routing, TLS termination, request-size limits. You will watch request-duration percentiles end-to-end and compare to app-level percentiles. |
| **Go app** | Black-box source of traffic. Two endpoints, one DB query each. You will load it and watch p50/p95/p99 separate. |
| **Postgres on PVC** | The slowest thing in the chain. You will watch `pg_stat_statements`, lock waits, connection pool saturation, and how PVC I/O shows up in node-exporter. |
| **Helm (Prometheus, Grafana, Alertmanager, exporters)** | How observability itself is deployed and versioned. You will watch what happens when a scrape interval misses a spike. |
| **Local OCI registry** | The release pipeline. You will build the app, push, and deploy by tag. You will watch what happens when the tag floats vs. pins. |

## What we will observe, in order

Topics attach to the stack in this order. Each topic doc links back to this map so you know *where in the running system* the concept lives.

1. **Project deploy** — build, push, deploy, verify. Then look at every panel in `grafana` and name the metric behind it.
2. **Latency percentiles** — read `http_request_duration_seconds_bucket` from the app and from NGINX. Compute `histogram_quantile(0.95, ...)`. Break the system and watch p50 stay flat while p99 explodes.
3. **Load balancing** — L4 (MetalLB) vs L7 (NGINX). Watch `nginx_ingress_controller_connections` vs `kube_pod_info`. Kill one app pod and see L4 keep sending to a down pod until health check notices.
4. **Database latency** — `pg_stat_statements_mean_exec_time` percentiles, `pg_stat_activity` connection count, lock-wait queries, replication lag (when you add a replica).
5. **Observability** — cardinality traps in labels, RED on the app, USE on the node, SLO definition from percentiles, alert on error-rate vs. on p95.
6. **Capacity** — Little's law on the app (L = λW), saturation curve as you raise RPS, queueing behaviour when the DB pool is full.

## The one rule for this repo

You are not here to "finish" the project. You are here to:

1. Build it once.
2. Break it on purpose, one way at a time.
3. Read the number that comes out of a Grafana panel or a `promql` query.
4. Ask: *what does this number mean, and when would I be woken up at 3am because of it?*

Every doc in this repo answers that question for one specific piece of the system.
