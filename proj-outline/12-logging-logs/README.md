# 12 — Logging: Loki (and the ELK question)

**Folder:** `12-logging-logs/`
**Milestone:** M11 — Logs

---

## Teach first: what a log pipeline must do

`kubectl logs` is fine for one pod. A log *pipeline* exists because you need to:

1. **Collect** logs from every pod on every node, continuously.
2. **Centralize** them in one queryable place (pods die, nodes restart, history vanishes).
3. **Structure** them — parse text into fields (level, request_id, user) so you can filter.
4. **Retain** them per policy (days for debug logs, longer for audit).
5. **Query** across services and time: "errors from outline-server with request_id=X in the last hour."

The pipeline shape, always:

```
app (stdout/stderr) → collector (DaemonSet) → storage/index → query UI (Grafana)
```

Note the first link: **apps log to stdout/stderr, always.** Kubernetes captures container stdout/stderr into node-local files (`/var/log/pods/...`); collectors tail those files. An app that logs to a file inside the container is invisible to this whole machinery — that's a doc 10 deployment concern (log to stdout).

---

## Loki vs. ELK — the decision, made explicitly

You asked about Logstash specifically. The two architectures:

| | **Loki + Promtail/Alloy** | **ELK (Elasticsearch + Logstash + Kibana)** |
|---|---|---|
| Index | Labels only (index is tiny) | Full-text index of every field (index is huge) |
| Resource cost | Light (single binary + object store) | Heavy (JVM, per-field indexing, disk-hungry) |
| Query language | LogQL (PromQL-flavored) | Lucene/KQL |
| Full-text search | Weak — you filter by labels, then grep | Excellent — any field, any term |
| Parsing | At query time (or ingest with `logql` pipeline stages) | At ingest (Logstash pipelines) |
| Ops surface | Small | Large (ES cluster tuning is a career) |
| Grafana integration | Native first-class | Good |

The architectural insight: **Elasticsearch indexes at ingest (expensive writes, fast any-field search); Loki indexes only labels at ingest (cheap writes, then grep-like scanning at query time).**

> **Tradeoff — the honest choice.** Loki is the right default here: cheaper to run, integrates with the Grafana/Prometheus you already have (doc 11), and label-based querying matches "show me errors from outline-worker" perfectly. ELK is the right answer when you need *adversarial* full-text search — "find me every log line in the fleet containing this correlation id" without knowing its labels — or when parsing at ingest (Logstash grok pipelines, enriching events as they flow) is a hard requirement. **Logstash itself — the ingest-parsing engine — is genuinely educational**: grok patterns, mutate filters, conditional routing are transferable concepts. **Plan: run Loki as the real pipeline (M11), then stand up a small ELK alongside it later as a comparison exercise — not both as production.** If you want the Logstash-style ingest-parsing experience inside Loki-land, Promtail's pipeline stages (regex, json, labels, timestamp) cover the same ground.

---

## Loki's model

Logs are grouped by **labels** — the same idea as Prometheus labels, and the trap:

```
{namespace="outline", app="outline-server"}   ← good: bounded values
{pod="outline-server-7d9f9-abcde"}            ← bad: one stream per pod name
```

Loki indexes **label sets** (streams); the log content itself is stored compressed (often in object storage — your MinIO, doc 08) and scanned at query time.

> **Failure mode — cardinality explosion, the Loki edition.** If you put high-cardinality values in labels (user id, request id, full pod name), you create one stream per value: ingest slows, index bloats, queries degrade. **Labels: namespace, app, level at most. Everything else stays *inside* the log line* and gets extracted at query time (or via Promtail pipeline stages into a few fixed labels). This is the #1 Loki operational mistake and it's the same lesson as Prometheus cardinality (doc 11) — internalize it once.**

### LogQL

```logql
# all errors from outline, last hour
{namespace="outline"} |= "error"

# parse JSON lines, filter by level, count per minute
{namespace="outline", app="outline-server"} | json | level="error" | line_format "{{.msg}}" 

# a request's trail across services
{namespace=~"outline|database"} |= "req_8f3a2c"
```

Read it as: *select streams by labels → filter/transform lines → aggregate.* The last query is the killer feature — cross-service correlation by an id in the log line, no indexing required.

---

## The collector: Promtail (or Alloy)

**Promtail** is the DaemonSet that tails `/var/log/pods` on every node, attaches Kubernetes metadata (namespace, pod, container) as labels, optionally parses lines (pipeline stages), and pushes to Loki.

```yaml
# promtail pipeline stages — the "Logstash experience", in Loki-land
- docker: {}                        # parse docker/json log lines
- json:
    expressions:
      level: level
      msg: msg
      requestId: req_id
- labels:
    level: ""                       # promote level to a label (bounded: info/warn/error)
- timestamp:
    source: timestamp
    format: RFC3339
```

> **Tradeoff — parse at ingest (pipeline stages) vs. at query time.** Ingest parsing makes queries fast and labels reliable, but a bad parse rule mangles logs irreversibly at write time. Query-time parsing is flexible and safe but slower. **Senior default: minimal ingest parsing (level, timestamp), everything else at query time.** You can always add a pipeline stage later; you can't un-mangle ingested logs.

*(Grafana Alloy is Promtail's successor for new deployments — same pipeline-stage model, more connectors. Either is fine; the concepts are identical.)*

---

## Retention and storage

- Loki stores chunks in object storage — point it at MinIO (`s3://loki-chunks`). Your doc 08 store becomes the substrate for logs too.
- **Retention** via compactor: e.g. 14d general, 30d for `audit` namespace labels.
- Size your expectations: a small cluster runs a few GB/day. **Set Loki's own disk/ingestion limits before it becomes the biggest thing in the cluster** (`ingestion_rate_mb`, per-tenant limits).

> **Threshold — log volume is a monitoring subject too.** A sudden 10× spike in lines/sec from one service is *itself a signal* (retry storm? debug flag left on? poison message loop from doc 10?). Put lines/sec per service on a dashboard. "Who is log-spamming right now" is a 3am question worth a panel.

---

## Structured logging — the app-side half

The pipeline can only be as good as the lines apps emit. Outline/Node.js emits JSON-ish logs (level, message); Postgres emits its own format; nginx the access-log format.

Rules that make everything downstream work:

1. **One line, one event.** Multi-line stack traces break line-based pipelines (Promtail has multiline stages to reassemble them — configure for Java/Node stack traces).
2. **JSON where possible** — parseable without regex.
3. **Stable field names** — `level`, `msg`, `req_id`, `user_id`, `duration_ms`.
4. **A correlation id per request** — this is what makes the cross-service LogQL query above possible. If Outline mints a `req_id` at ingress and includes it in every log line (and to Postgres via `application_name` or comment), you can follow one user action from browser → server → worker → DB.
5. **Never log secrets** — tokens, passwords, Authorization headers, PII you don't need. Your JWTs (doc 09) will appear in access logs if you're careless; scrub at the app, not the pipeline.

> **Senior lens** — logs are the *only* pillar that can answer "what exactly happened in this one case?" Metrics say latency spiked; logs say it was this user, this endpoint, this error. That specificity is why the correlation-id discipline above pays more than any tooling choice.

---

## Grafana as the single pane

By M11's end, Grafana queries both Prometheus (metrics) and Loki (logs) — and **explored metrics→logs correlation**: click a latency spike on the RED dashboard, "Explore logs for this label set and time range." One tool, two pillars, linked by shared labels (`namespace`, `app`). This is the payoff of using the same label vocabulary everywhere — a convention to enforce from day one.

---

## The workflow you'll live in

```
# Query in Grafana Explore (LogQL), or CLI:
logcli query '{namespace="outline"} |= "error"' --since=1h

# Check collector health:
kubectl -n logging logs ds/promtail --tail=50
# Promtail UI (targets): port-forward to the daemonset pod :9080/targets

# Loki status:
kubectl -n logging port-forward svc/loki 3100
curl -s localhost:3100/ready
curl -s localhost:3100/metrics | grep loki_distributor_lines_received_total
```

---

## Failure modes you must deliberately cause

1. **Flood Loki** (a pod logging in a tight loop) → watch ingestion limits reject/drop, and the lines/sec panel catch it. Learn where dropped logs go (`loki_distributor_discarded_samples_total`).
2. **Add a high-cardinality label** (pod name) → watch stream count explode; feel the query slowdown; then fix labels.
3. **Kill a Promtail pod** → logs from that node stop; verify the gap is visible (a monitoring gap is a blind spot you must know about).
4. **Corrupt/incompletely-parse lines** (mixed JSON and text from one app) → see query-time parsing fail; decide between fixing the app's output or adding a pipeline stage.
5. **Restart Loki with full object storage** → verify history survived; then delete the PVC (in a drill) and verify MinIO-based recovery.
6. **Query without label filters** → experience a slow full-scan; learn why queries always narrow by labels first.

---

## Exit criteria for M11

- [ ] Loki + Promtail (or Alloy) deployed, storing chunks in MinIO with retention configured
- [ ] Every namespace's logs queryable in Grafana with consistent labels
- [ ] Pipeline stages promoting `level` and timestamps; multiline handling for stack traces
- [ ] Cross-service correlation query works: one `req_id` traced through server → worker → dependency
- [ ] Log volume per service on a dashboard; ingestion limits set and tested
- [ ] Deliberate comparison made: you can articulate *when* you'd need ELK/Logstash instead (and have optionally run it once)

Next: `13-node-health` — the machines under everything.
