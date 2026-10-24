# Observability — Datadog, Postgres, Kafka, Dashboards

> The three pillars — **metrics, logs, traces** — applied to this system, with the
> specific signals for Postgres, Kafka, and the app. Includes the charts you asked
> for (Kafka streams, ingress, latency, egress) and answers the Datadog-locally
> question.
>
> **Related deep-dive folders:** Postgres internals
> ([`postgres/tuning-and-observability.md`](postgres/tuning-and-observability.md))
> and NGINX/edge metrics
> ([`nginx/tuning-and-observability.md`](nginx/tuning-and-observability.md))
> cover the same signal types from the "how it actually works" angle.

---

## 1. The three pillars (and what each is for)

| Pillar | Answers | Examples here |
|--------|---------|---------------|
| **Metrics** | "Is it healthy, and is it changing?" | request rate, error rate, DB connections, Kafka lag |
| **Logs** | "What happened in this specific case?" | a failed publish, a validation error, an archive run |
| **Traces** | "Where did the time go across services?" | SPA → API → Postgres → outbox; consumer → DB |

**Rule:** alert on **metrics** (symptoms), investigate with **logs** and **traces**
(causes). Don't alert on raw logs; don't diagnose from a metric alone.

---

## 2. "Datadog on local — is it supported?"

Short answer: **yes, the Datadog Agent runs locally and on k3s**, but with caveats you
should decide on deliberately.

- **The Datadog Agent** is a single process (container) that collects metrics, logs,
  and traces from the host and your containers. It runs fine on a single node and in
  k3s via the official Helm chart. This is the supported, standard path.
- **Data goes to Datadog's SaaS backend** — you need a Datadog account and API key.
  There's no fully self-hosted "Datadog server"; the agent is local, the backend is
  theirs. The free tier covers a single host, which is enough for learning.
- **What this means for you:** you get real dashboards, real alerting, and real APM —
  excellent for learning — at the cost of shipping your (personal) metrics to a third
  party. For an expense tracker with your own financial data, be deliberate: send
  **metrics and traces**, and think hard before sending **logs** (they may contain
  personal data). Datadog has log-scrubbing config; use it.

**The alternative you should also know:** the **Prometheus + Grafana** stack, fully
self-hosted on your k3s node. `prometheus` scrapes exporters (including the Datadog
agent's Prometheus endpoint, or `postgres_exporter` and Kafka's JMX exporter directly),
Grafana visualizes. Nothing leaves your network. More setup, zero third-party data
sharing.

**Recommendation for learning both:** run **Grafana + Prometheus** as the backbone
(scrape everything), and *optionally* add the **Datadog agent** so you can compare a
managed APM against self-hosted. Learn the exporter/ Prometheus model first (it's
portable), then see what Datadog adds on top. Record the choice in
[`design.md`](design.md). Either way, the *signals* below are what you monitor — the
tool is secondary.

---

## 3. Application metrics (the API and consumer)

**The RED method** (Rate, Errors, Duration) for every service:

- **Rate** — requests/sec (per endpoint).
- **Errors** — error rate, by status code (5xx vs 4xx separated — 4xx is often client
  error, 5xx is your bug).
- **Duration** — latency percentiles: **p50, p95, p99**. Never alert on the mean; the
  tail is what users feel.

**Use the USE method** (Utilization, Saturation, Errors) for resources: CPU, memory,
connection pool usage (saturation of the pool is a leading indicator of DB trouble).

**App-specific signals:**
- **Outbox depth** — unsent outbox rows. **This is your most important app metric.**
  Rising depth = the relay can't publish (Kafka down or slow). Alert on it.
- **Outbox age** — age of the oldest unsent row. Depth can look fine while a single
  old row is stuck (a poison message). Alert on age too.
- **DLQ depth** — dead-lettered events. Any sustained value = investigate.
- **JWT failures** — 401 rate spikes = token expiry issues or an attack.
- **Rate-limit hits (429)** — from both DRF and NGINX.

---

## 4. Postgres observability (from [`postgres-guide.md`](postgres-guide.md) §5)

**Enable `pg_stat_statements` on day one.** Then export via `postgres_exporter`.

| Signal | Source | Why it matters |
|--------|--------|----------------|
| Connections (used/max) | `pg_stat_activity` | pool exhaustion; PgBouncer health |
| Cache hit ratio | `pg_stat_database` | should be >0.99 warm; drops = memory/IO problem |
| Transactions/sec | `pg_stat_database` | throughput baseline |
| Dead tuples / bloat | `pg_stat_user_tables` | vacuum falling behind → performance decay |
| Seq vs index scans | `pg_stat_user_tables` | climbing seq scans = missing index |
| Slow queries | `pg_stat_statements` | by `total_exec_time` — your optimization list |
| Lock waits | `pg_stat_activity`, `pg_locks` | contention; blocked queries |
| Checkpoint frequency | `pg_stat_bgwriter` | checkpoint storms = WAL/tuning issue |
| Replication lag | `pg_stat_replication` | (when you add replicas) |
| Table/index sizes | `pg_total_relation_size` | growth trend → lifecycle working? |

**Alerts to set:** cache hit ratio dropping, connections near max, dead tuples
climbing on a hot table, replication lag (later), long-running queries.

---

## 5. Kafka observability (the charts you asked for)

You specifically want charts for **streams, ingress, latency, and egress**. Here's how
each maps to real Kafka signals:

### Consumer lag (the #1 signal)
- **Definition:** latest offset − committed offset, per partition/group.
- **Source:** consumer group metrics, or `kafka_exporter` (scrapes group offsets).
- **Alert on:** lag rising, or lag above a threshold for N minutes. Lag = consumers
  falling behind = loan balances going stale. This is your most important Kafka alert.
- **Chart:** lag over time, per consumer group and topic.

### Throughput — ingress and egress
- **Ingress (produce rate):** messages/sec and bytes/sec produced, per topic. Your
  "streams coming in" chart.
- **Egress (consume rate):** messages/sec and bytes/sec consumed, per consumer group.
  Your "streams going out" chart.
- **The relationship:** if ingress > egress sustained, lag grows — the classic
  "consumers can't keep up" picture. Chart them together.
- **Source:** broker JMX metrics (via a JMX/Prometheus exporter) or `kafka_exporter`.

### Latency
- **Produce latency** — time from producer send to broker ack.
- **Consume/processing latency** — time from consume to offset commit (your consumer's
  work).
- **End-to-end latency** — `produced_at` (in the event envelope, see
  [`avro-guide.md`](avro-guide.md) §3) to processing time. This is the one users feel:
  "how stale is my loan balance?" Chart p50/p95/p99.
- **Source:** client metrics + the envelope timestamp trick.

### Broker health
- **Under-replicated partitions** — should be zero. Non-zero = replication trouble
  (moot on one node, critical in prod).
- **Offline partitions** — should be zero.
- **Request rates and handler idle %** — broker saturation.
- **Log/disk usage** — retention working? disk filling?
- **Source:** broker JMX metrics.

### Schema registry
- **Registration rate, compatibility failures** — a compatibility failure means someone
  tried a breaking schema change ([`avro-guide.md`](avro-guide.md) §5). Alert on it.

**A concrete dashboard layout** (build in Grafana or Datadog):
1. **Kafka overview** — produce rate, consume rate, lag, under-replicated partitions.
2. **Latency** — produce p99, consume p99, end-to-end p99.
3. **Per-topic** — ingress/egress bytes, message rate, retention/disk.
4. **Consumer group** — lag per partition, rebalance frequency.

---

## 6. NGINX / edge metrics

- **Request rate, error rate (5xx), latency** — same RED method, at the edge. This is
  the user's-eye view.
- **Rate-limit hits** — 429s from NGINX (distinct from DRF's 429s).
- **Upstream health** — connections to the API, upstream failures.
- **TLS** — handshake failures, cert expiry (alert before it expires!).

---

## 7. Lifecycle / archival observability (from [`data-lifecycle.md`](data-lifecycle.md) §6)

- **Archive job success/failure** — alert on failure (a failed archive blocks the safe
  partition drop).
- **Partitions detached/dropped over time** — is the archiver keeping up?
- **Hot table sizes** — should plateau, not grow forever.
- **Reconciliation drift** — alert the moment a loan's balance != sum of its changes.
- **Kafka retention expirations** — messages expiring before consumption = lag problem.

---

## 8. Logging strategy

- **Structured logs (JSON)** from the API and consumer — parseable by your pipeline.
- **Correlation IDs** — propagate a request/trace id from the SPA through the API into
  the event envelope, so you can follow one expense end-to-end across the async
  boundary. This is the logging counterpart to traces.
- **Log levels** used deliberately; don't log PII or secrets. For financial data,
  log *ids and amounts*, not card numbers or tokens.
- **Postgres slow-query log** (`log_min_duration_statement`) — your cheapest continuous
  profiler ([`postgres-guide.md`](postgres-guide.md) §5).
- **Centralize** — ship logs to your chosen backend (Datadog, or Loki+Grafana
  self-hosted).

---

## 9. Tracing (optional but high-value)

The async boundary makes this system hard to debug without traces. A single expense
touches: SPA → NGINX → API → Postgres → outbox → relay → Kafka → consumer → Postgres.
**Distributed tracing** (OpenTelemetry, exported to Datadog or Jaeger/Tempo) stitches
these into one trace via correlation IDs.

**Do metrics and logs first; add tracing when the async flow gets confusing** (it
will). But design the **correlation ID into the event envelope from day one** — it's
nearly free to include and painful to retrofit.

---

## 10. Alerting philosophy

**Alert on symptoms, not causes.** "Loan balance is stale" (consumer lag) is a symptom
users feel; "CPU is at 70%" is a cause they don't. A few good alerts beat fifty noisy
ones.

**Starter alert set for this project:**
- Consumer lag above threshold for N minutes → loan balances stale.
- Outbox depth or age rising → publishing failing.
- DLQ depth > 0 → poison messages.
- API 5xx rate spike → your bug.
- API p99 latency above threshold → degradation.
- DB connections near max → pool trouble.
- Cache hit ratio dropping → memory/IO problem.
- Dead tuples climbing on a hot table → vacuum trouble.
- Reconciliation drift detected → data integrity.
- Archive job failed → lifecycle broken.
- Cert nearing expiry → edge trouble.

**Every alert needs a runbook** ([`runbooks.md`](runbooks.md)): what it means, first
thing to check, how to fix. An alert without a runbook is noise.

---

## 11. Exercises (Phase 12)

1. **Enable `pg_stat_statements`**, export via `postgres_exporter`, build a Postgres
   dashboard. Find your slowest query. *Lesson: DB observability.*
2. **Export Kafka metrics**, build the four charts (lag, ingress, egress, latency).
   Throttle the consumer and watch lag climb. *Lesson: Kafka observability.*
3. **Structured logs + correlation ID** — follow one expense from SPA to loan update
   via its ID. *Lesson: observability across the async boundary.*
4. **Set the starter alerts**, then trip each one on purpose and write its runbook.
   *Lesson: alerting as a discipline.*
5. **Compare Datadog vs Grafana** for one dashboard. *Lesson: managed vs self-hosted
   trade-offs.*

---

## 12. Decisions to record in `design.md`

- Datadog, Grafana+Prometheus, or both — and the data-sharing trade-off accepted.
- Which pillars you ship where (esp. logs and PII).
- The correlation-ID field in the event envelope.
- The starter alert set and thresholds.
- Dashboard layout (Kafka, Postgres, app, edge).
- Whether/when you add tracing.
