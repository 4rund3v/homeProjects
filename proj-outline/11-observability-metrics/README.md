# 11 — Observability: Metrics with Prometheus and Grafana

**Folder:** `11-observability-metrics/`
**Milestone:** M10 — Metrics

---

## Teach first: what observability actually means

**Monitoring** answers "is it up?" **Observability** answers "why is it slow/broken/weird?" — from the outside, using the system's own outputs.

The canonical three pillars (each with distinct failure-detecting power):

| Pillar | Question it answers | Tool here |
|---|---|---|
| **Metrics** | What is the *rate/shape* of behavior over time? | Prometheus + Grafana |
| **Logs** | What did this one request/component *say*? | Loki (doc 12) |
| **Traces** | Where did time go *across* components? | (out of scope; noted at the end) |

This doc is metrics. Metrics are numeric time series: `(name, labels, timestamp, value)`.

---

## The Prometheus model

Prometheus is **pull-based**: it scrapes an HTTP endpoint (`/metrics`) on each target every N seconds. Targets expose metrics in a simple text format:

```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="POST",path="/api/docs",status="200"} 5412
http_request_duration_seconds{method="POST",quantile="0.5"} 0.012
http_request_duration_seconds{method="POST",quantile="0.99"} 0.145
```

Two data types carry most of the weight:

- **Counter** — only goes up (requests, errors, bytes). Meaningful only as a *rate* (`rate()`).
- **Gauge** — a value at a point in time (queue depth, memory used, connections).
- **(Histogram** for latency distributions — needed for p50/p99.)

> **Histogram vs. Summary — the distinction a panel will probe, and the trap it hides:**
> - A **`Summary`** is computed *client-side*: the exporter precomputes `quantile=0.5` and `quantile=0.99` (lines 32–33 above). You can read them directly — but you **cannot** aggregate them across instances. A p99 computed on instance A and a p99 on instance B do *not* average into a fleet p99. Summaries give you per-instance percentiles only.
> - A **`Histogram`** exports **buckets** (`_bucket`), a cumulative count per boundary (`le="0.1"` = "requests ≤ 100ms"), plus `_sum` and `_count`. Because buckets are *counts*, Prometheus can add them *across* instances and then compute a true fleet-wide percentile with `histogram_quantile` (line 51). **That's the whole reason the `histogram_quantile(0.99, rate(..._bucket[5m]))` example on line 51 assumes a `_bucket` histogram — not a Summary.**
>
> **The trap a cold reader hits:** copy the line-51 query, run it against a *Summary* (which has `quantile=` labels, no `_bucket`), and get `NaN` — because `histogram_quantile` needs buckets and there are none. **If your app exposes a Summary, do NOT use `histogram_quantile`; read the `quantile=` series directly.** If it exposes a Histogram (most modern exporters, incl. the Prometheus client libraries' default), `histogram_quantile` works but only as accurately as your bucket boundaries — p99 needs a bucket near your target, else you interpolate coarsely.

> **Senior lens — count it, don't gauge it.** For anything that happens (requests, failures, jobs), expose a counter, not a gauge updated periodically. Counters are lossless under scrape intervals; a gauge "set every 10s" loses everything between samples, and you can't `rate()` it. This is the single most common instrumentation mistake.

### The other half: PromQL

```promql
# error rate (5xx per second) over the last 5m
rate(http_requests_total{status=~"5.."}[5m])

# 99th percentile latency from a histogram
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# queue depth right now
outline_queue_depth{queue="emails"}

# saturation: memory usage as fraction of limit
container_memory_working_set_bytes{pod=~"outline-.*"}
  / on(pod) container_spec_memory_limit_bytes{pod=~"outline-.*"}
```

Read `rate(x[5m])` as "the per-second rate of x's increase over the last 5 minutes." Every dashboard and alert is PromQL under the hood.

---

## The stack you'll deploy

**kube-prometheus-stack** (one Helm chart) installs:

| Component | Job |
|---|---|
| **Prometheus** | scrapes and stores metrics (local TSDB) |
| **Alertmanager** | receives alerts from Prometheus rules; routes/dedupes/notifies |
| **Grafana** | dashboards on top of Prometheus (and Loki) |
| **node-exporter** (DaemonSet) | per-node hardware metrics: CPU, memory, disk, network |
| **kube-state-metrics** | *cluster* state as metrics: replicas desired vs. ready, pod restarts, PVC usage |
| **Prometheus Operator** | manages Prometheus/Alertmanager via CRDs (`PodMonitor`, `PrometheusRule`, ...) |

The distinction worth burning in:

> **node-exporter = the machine's health. kube-state-metrics = Kubernetes's opinion of your objects.** "Node is at 90% disk" is node-exporter. "Deployment has 2/3 ready replicas" is kube-state-metrics. You need both — a cluster where every node is healthy but `kube_replicas_unavailable` is 1 is still broken.

### ServiceMonitors — how apps get scraped

The Prometheus Operator CRD that says "scrape this":

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: outline
  labels: { release: kube-prometheus-stack }   # must match the stack's selector!
spec:
  selector:
    matchLabels: { app: outline }              # picks the Service
  endpoints:
  - port: http
    path: /metrics
    interval: 30s
```

> **Failure mode — the invisible ServiceMonitor.** You create it, Prometheus ignores it. 90% of the time the `metadata.labels` don't match the release label the Prometheus instance selects on (`release: kube-prometheus-stack` by default). Prometheus's **Targets page** (web UI → Status → Targets) is where you see what's actually being scraped — check it before debugging anything else.

---

## The USE/RED method: what to put on dashboards

Two complementary checklists prevent "pretty but useless" dashboards:

**RED** (for *services* — request-driven, user-facing):
- **Rate** — requests/sec
- **Errors** — error rate/percentage
- **Duration** — latency (p50, p99)

**USE** (for *resources* — nodes, Postgres, Redis):
- **Utilization** — % used
- **Saturation** — queued/deferred work (queue depth, run queue, waiting connections)
- **Errors** — device/script errors

Every panel on a dashboard should come from one of these lists. If you can't say which cell of USE/RED a panel answers, delete it.

### The dashboards you'll build (in this order)

1. **Platform overview** — node CPU/mem/disk (node-exporter), cluster capacity, pods per node
2. **Kubernetes detail** — per-namespace: restarts, unavailable replicas, PVC usage %, HPA behavior
3. **Outline service (RED)** — req/s by status class, error %, p50/p99 latency, WebSocket connections
4. **Outline workers** — queue depth per queue, job duration, job failures, oldest pending job
5. **Postgres (USE)** — connections (idle/active vs. max), transaction rate, replication lag, cache hit ratio, WAL generation, disk %
6. **Redis (USE)** — memory vs. maxmemory, evicted keys, keyspace hits/misses, connected clients, replication
7. **Delivery** — Jenkins build duration/success rate, Harbor disk, image pull times

> **Senior lens — a dashboard is an argument.** Good dashboards aren't a pile of graphs; each one answers a *specific question an on-call engineer will ask at 3am*: "Is it me or the user? Is it app or DB? Is it now or always?" Group panels to walk that decision tree — RED first (is the symptom real?), then dependencies in order of probability. If a dashboard doesn't change a decision during an incident, it's decoration.

> **Threshold — sensible alerting starting points** (tune to your baselines, these are starting points not gospel):
> - Node: disk > 80% (page), > 90% (urgent); memory > 90% sustained 10m; CPU load > cores for 15m
> - PVC: > 80% used (this catches the doc 06 "2× headroom" rule before it's fatal)
> - Pod: restarts > 3 in 15m (crashloop); replicas unavailable > 5m; not Ready for 10m
> - App (RED): 5xx rate > 1% for 10m; p99 > 1s for 15m; error *spike* (rate doubles vs. 1h ago)
> - Workers: queue depth > threshold for 30m (tune per queue); oldest job age > 15m; zero jobs processed in 1h while depth > 0 (stuck)
> - Postgres: connections > 80% of max; replication lag > 30s; disk > 80%
> - Redis: memory > 90% of maxmemory; evictions > 0 on queue DB (should never happen with `noeviction` — an eviction alert on a *cache* is fine, on a *queue* is an incident)
>
> **Alert on symptoms, not causes.** "Disk 85%" matters because it will cause writes to fail — that's the alert. "Postgres restarts = 1" is a cause; alert on "replication lag high" instead.

---

## Recording rules — precompute what dashboards need

Every dashboard panel running `rate(...[5m])` on the fly gets expensive. **Recording rules** precompute expressions into new time series on a schedule:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: outline-rules
spec:
  groups:
  - name: outline.recording
    interval: 30s
    rules:
    - record: job:http_errors:rate5m
      expr: sum by (job) (rate(http_requests_total{status=~"5.."}[5m]))
```

Dashboards then query `job:http_errors:rate5m` — cheap, consistent, and the PromQL logic lives in versioned code, not pasted into N dashboard panels.

> **Naming convention** `level:metric:operations` (`job:http_errors:rate5m`) is the community standard — read others' rules fluently by learning it once.

---

## Alertmanager: routing and noise control

A `PrometheusRule` with `alert:` fires → Alertmanager → routes by labels:

```yaml
route:
  receiver: default
  routes:
  - match: { severity: page }
    receiver: pager          # e.g. a webhook → phone/Slack
  - match: { severity: ticket }
    receiver: tracker        # next-day issue
```

The two knobs that decide whether alerting survives contact with reality:

- **`for:`** — how long a condition must hold before firing. Without it, every transient blip pages you. **Almost every alert should have `for:` between 2m and 15m.**
- **inhibition** — when a "bigger" alert fires, silence dependent "smaller" ones (node down ⇒ inhibit all pod alerts on that node). Without inhibition, one node death pages you 40 times.

> **Failure mode — alert fatigue.** The death spiral: too many noisy alerts → everyone ignores them → the one real alert is missed. When an alert fires and your honest reaction is "ugh, that again," fix or delete it *that day*. An alert you ignore is worse than no alert — it trains ignore-reflexes. Periodically review: every alert should be **actionable** (a runbook exists), **rare** (it pages when something's truly wrong), and **symptom-based**.

---

## Retention and cardinality — the two resource levers

- **Retention** — Prometheus local TSDB keeps data N days (default 15d). More retention = more disk. For a homelab, 15-30d is plenty; long-term storage (Thanos/Mimir) is a later project.
- **Cardinality** — the number of *distinct time series*. Every unique label combination is a series. `http_requests_total{path=...}` with 10k untemplated paths = 10k series and a dying Prometheus.

> **Threshold — cardinality budget.** Rule of thumb: a healthy small setup stays under ~1-2M active series; watch Prometheus's own metrics (`prometheus_tsdb_head_series`, `scrape_series_added`). The usual culprit is an app label with unbounded values (path, user id, session id). **Template high-cardinality labels** (`/docs/:id` not `/docs/12345`) at the app or relabel stage. This is the Prometheus failure mode that looks like "Prometheus is randomly OOM-killed."

---

## What about traces?

Distributed tracing (Tempo, Jaeger) answers "this request was slow — *which span* was slow?" across services. For this single-app + dependencies topology, RED + logs covers 90% of debugging. Add tracing when you have multi-service request paths; the natural entry point later is OpenTelemetry instrumentation of Outline's server.

---

## The workflow you'll live in

```
# Prometheus UI (port-forward):
kubectl -n monitoring port-forward svc/kube-prometheus-stack-prometheus 9090:9090
# → Status → Targets: is everything scraped?
# → Status → TSDB: head series (cardinality check)
# → Alerts: what's pending/firing?

# Grafana:
kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80

# Fire a test alert into Alertmanager:
amtool alert add TestAlert severity=page
```

---

## Failure modes you must deliberately cause

1. **Delete/stop a ServiceMonitor's target pod** → watch it vanish from Targets; dashboards gap. Prometheus doesn't alert by default on "target down" — add an `up == 0` alert for critical targets.
2. **Introduce a high-cardinality label** (e.g. re-label with pod name on a busy metric) → watch `head_series` climb and Prometheus memory follow. Then fix with relabeling.
3. **Fill a disk past 80%** → your PVC alert should fire *before* anything breaks. Verify page vs. ticket routing.
4. **Kill a node** → observe node-exporter gaps, kube-state-metrics showing pods Pending, and inhibition suppressing the pod-alert storm. If you got 40 pages, fix inhibition.
5. **Set `for:` too low on a flappy metric** → experience alert noise; then tune.
6. **Restart Prometheus** → verify TSDB persistence (it needs a PVC) and that dashboards/history survive.

---

## Exit criteria for M10

- [ ] kube-prometheus-stack installed via Helm (in Terraform, doc 01) with persistent storage
- [ ] All components scraped — verified on the Targets page (nodes, kube-state, Postgres, Redis, Outline, Jenkins, Harbor)
- [ ] The 7 dashboards above built, each panel traceable to USE/RED
- [ ] Recording rules in versioned `PrometheusRule`s, not pasted PromQL
- [ ] Alertmanager routing configured (page vs. ticket) with `for:` and inhibition
- [ ] One alert intentionally fired and routed correctly end-to-end
- [ ] Cardinality inspected and under budget; retention configured deliberately

Next: `12-logging-logs` — the second pillar.
