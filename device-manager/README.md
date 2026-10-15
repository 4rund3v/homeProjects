# Device Manager — Network Device Intelligence Platform

Build a production-grade network observability platform. Learn the architecture, patterns, and operational practices that separate a working prototype from something you can run in an enterprise at 3 AM without panicking.

---

## What This Project Builds

A system that continuously discovers devices on your LAN/WiFi, fingerprints them (MAC, IP, hostname, vendor), persists observations in a relational database, and surfaces them on a live dashboard. A user clicks "trace," the system scans the subnet, and new devices appear in the browser in real time.

What makes this project different from a tutorial is the bar. It is designed to the standard of a production system in an enterprise — observable, reliable, secure, deployable. A junior dev gets it to work. A senior dev gets it to work at 3 AM when something is broken, and knows it is broken before the page fires.

---

## Production Topology

```
                        Internet
                           |
                    +------v------+
                    |    Nginx    |  TLS termination, WS proxy, static files
                    |  (ingress)  |
                    +------+------+
                           |
              +------------+------------+
              |                         |
      +-------v--------+      +---------v--------+
      |   DRF (HTTP)   |      |   ASGI worker    |  Holds WS connections
      |  uvicorn x3    |      |   (Channels)     |  Subscribed to Redis pub/sub
      |  stateless     |      |   fixed replicas |  Long grace period + PDB
      +-------+--------+      +---------+--------+
              |                         ^
              | enqueue                 | push
              v                         |
      +---------------+       +---------+--------+
      | Celery worker |       |      Redis       |
      | x2 (trace-    |       |  - cache         |
      |   queue)      |       |  - broker        |
      +-------+-------+       |  - pub/sub       |
              |               +------------------+
              | gRPC (mTLS)
              v
      +---------------+
      | nettrace      |
      | Go service    |
      | ARP/mDNS/     |
      | NetBIOS scan  |
      +-------+-------+
              |
              | Avro
              v
      +---------------+       +------------------+
      |     Kafka     |------>|  Three consumers |
      |  device-      |       |  ingestion       |
      |  findings     |       |  Faust stream    |
      |  3 partitions |       |  metrics         |
      +---------------+       +--------+---------+
                                      |
                                      v
                            +------------------+
                            |   PostgreSQL     |
                            | devices, events, |
                            | vendors, auth    |
                            +------------------+
```

---

## How Data Flows — The Live Trace Scenario

Every component exists to serve one step in this flow. Understanding this sequence is understanding the architecture.

1. User clicks Trace. Browser sends `POST /api/trace/` with a JWT in the `Authorization` header.
2. Nginx terminates TLS and proxies to DRF.
3. DRF validates the JWT, checks the `trace:execute` scope, enqueues a Celery task, returns `202 Accepted + task_id`. The HTTP handler finishes in milliseconds.
4. Celery worker picks up the task from the Redis broker queue and calls the Go service over mTLS gRPC.
5. nettrace (Go) scans ARP + mDNS + NetBIOS in parallel goroutines, encodes each finding as Avro, and publishes to Kafka topic `device-findings` keyed by MAC.
6. Three consumers read the same topic independently:
   - Ingestion consumer calls `DeviceService.ingest()`, writes to Postgres, then publishes `DeviceUpdated` to Redis pub/sub.
   - Faust processor maintains a "new devices per minute" tumbling window and materializes it into Postgres.
   - Metrics consumer counts findings by vendor and emits Datadog gauges.
7. The ASGI worker, subscribed to the `ws-events` channel, receives the push and fans it out to every connected WebSocket client.
8. The browser updates the dashboard in place. No reload.

**Why each piece exists:**
- Celery decouples the HTTP request from long-running work, so the uvicorn worker is never blocked and retries/timeouts belong to the queue.
- Kafka is a durable, replayable log — add a fourth consumer later without touching the producer.
- Redis serves three distinct roles with three distinct reliability profiles.
- The ASGI worker is separate from the HTTP handler because their lifecycles differ.

---

## Junior vs. Senior — The Five Dimensions This Project Targets

A junior builds the happy path. A senior builds the failure path and makes it visible.

### Observability
Junior: print statements, no traces, no metrics. When the dashboard shows zero devices and you know the scan found forty, you grep logs.

Senior: distributed traces crossing Go, Kafka, Celery, and Postgres in one flame graph. Structured JSON logs keyed by mac, subnet, and task_id. Custom metrics with SLO targets. When the dashboard shows zero devices, you open one trace and see the consumer is twelve thousand messages behind — no logs read.

### Reliability
Junior: Kafka down, endpoint 500s. Redis down, cache lookups crash. Go binary hangs, Celery task hangs until timeout and occupies a worker slot forever. Failures cascade.

Senior: every external dependency degrades gracefully. Kafka down, fall back to direct Postgres write, queue locally, replay on recovery. Redis down, bypass cache, emit `redis_unavailable`. Go hangs, hard timeout at fifteen seconds, kill the subprocess, return partial results, emit `trace_timeout`. The system gets less useful, not more broken.

### Data correctness
Junior: every trace publishes findings, the same device twice writes two events, consumer redelivery creates duplicates. Data is mostly right.

Senior: idempotency keys `(mac, observed_at, source)` with conflict-do-nothing. Kafka offsets committed only after the DB write succeeds. A schema registry enforces that producers and consumers cannot silently drift. An audit log records who triggered each trace with user, timestamp, subnet, duration, and device count.

### Security
Junior: anyone who can reach the API can run a trace. No auth on WebSockets. Logs do not record who did what.

Senior: JWT plus OAuth2 scopes — the trace endpoint requires `trace:execute`, the device list requires `device:read`. mTLS between the Go service and the Python backend, so only services with a CA-signed client certificate can inject findings. Per-user rate limiting. Multi-tenant row-level security in Postgres.

### Operational readiness
Junior: deploy by SSH and `git pull`. Secrets in a dotenv on the server. No monitoring. Find out it is broken Monday morning.

Senior: Helm charts with per-environment values files. Terraform provisions the cluster, networking, and TLS. Health checks at every layer. Graceful shutdown — SIGTERM drains in-flight tasks before exit. Alerting with runbooks on consumer lag, task failure rate, Redis memory, and replication lag. Secrets injected at runtime, never in Git.

---

## What You Will Learn

| Skill | Where it appears | Why it matters |
|---|---|---|
| Python design patterns | Domain/Application/Infrastructure layering | Testability without a framework; the same mental model as enterprise Java/C# services |
| Repository + Strategy patterns | Domain ABCs, infrastructure adapters | Swap real Postgres for an in-memory fake in tests; swappable vendor lookup |
| Apache Avro | Schema file, Go encoder, Python decoder | Binary wire format with schema evolution; the Kafka ecosystem's native format |
| gRPC | Proto, Go server, Python client | Polyglot RPC with strong typing; streaming for real-time findings |
| Apache Kafka | Topics, producers, consumers, consumer groups | Durable ordered event log; multiple independent consumers; replay |
| Kafka Streams / Faust | Windowed aggregations, state stores | Materialized views over the event stream; the Streams-Table-Join pattern |
| Redis | Cache, broker, pub/sub | Read-through cache; broker between DRF and Celery; in-process event bus |
| Django REST Framework | ViewSets, serializers, JWT + OAuth2 | Standard Python API layer with auth, pagination, permissions |
| JWT + OAuth2 | Token endpoint, scopes, resource-server validation | Who you are versus what you are allowed to do; the enterprise auth standard |
| WebSockets + Django Channels | Live dashboard updates | Push events to browsers without polling |
| uv + ruff | Python toolchain | Modern replacement for pip, venv, black, flake8, isort |
| PostgreSQL + Alembic | Migrations, partitioned tables | Durable state with schema versioning |
| Datadog APM | ddtrace, structured logs, custom metrics | Traces across service boundaries; SLO-driven alerting |
| Terraform | Cluster, networking, TLS provisioning | Reproducible infrastructure as code |
| Helm | Charts per environment | Deploy to dev, staging, and prod with the same manifests |
| Nginx + TLS | Ingress, cert-manager, WebSocket proxy | TLS termination, load balancing, static file serving |
| Observability as a first-class concern | Traces, metrics, logs, health checks | The difference between works-on-my-laptop and runs-in-production |

---

## The Docs

| File | Contents |
|---|---|
| README.md | This file. Overview, topology, the junior/senior framing, tech stack, env vars |
| ARCHITECTURE.md | Design patterns used, what you gain from each technology, and end-to-end request path walkthroughs (trace, read, WebSocket, failure paths, Faust windows) |
| DESIGN.md | Every architectural decision, why it was made, what alternatives were rejected |
| LAYOUT.md | Folder-by-folder map, what goes where, import rules, how it maps to production |
| PHASES.md | Build order, zero to fourteen, each with goals, learning, and acceptance criteria |
| INFRA.md | Docker Compose, k8s manifests, Helm chart structure, Terraform modules |
| OPERATIONS.md | Health checks, graceful shutdown, backup and restore, alerting runbooks |

---

## Tech Stack Summary

| Layer | Choice | Role |
|---|---|---|
| Python runtime | 3.12, uv, ruff | Primary implementation language |
| Web framework | Django + DRF | HTTP API, auth, admin |
| WebSockets | Django Channels on ASGI | Pushes live device events to browsers |
| Task queue | Celery + Redis broker | Long-running trace tasks, retries, scheduled jobs |
| Database | PostgreSQL 16 | Durable device state, event log, auth tables |
| Migrations | Alembic | Schema versioning |
| Cache + pub/sub + broker | Redis 7 | Read-through cache; pub/sub between Celery and ASGI; broker queue |
| Event log | Kafka 3.x in KRaft mode | Durable ordered stream of device findings |
| Stream processing | Faust | Windowed aggregations, materialized views |
| Wire format | Apache Avro | Binary encoding for DeviceFinding; schema evolution |
| RPC | gRPC | Go server, Python client, streaming option |
| REST validation | Pydantic | Request/response validation at the DRF boundary |
| Auth | JWT via SimpleJWT, OAuth2 via Keycloak | Token-based auth with scopes; resource-server pattern |
| Observability | ddtrace + Datadog Agent | Distributed traces, custom metrics, structured logs |
| Logging | structlog | Structured JSON logs consumable by Datadog without transformation |
| Go binary | Cobra CLI, gRPC server | Network discovery, Avro encoding, Kafka production |
| Frontend | React via Vite + Recharts | Device table, vendor pie, timeline, alerts |
| Ingress | Nginx + cert-manager | TLS termination, WebSocket proxying, static files |
| Deploy | Helm charts | Per-environment configuration |
| Infrastructure | Terraform | Cluster, VPC, DNS, TLS certs, IAM |
| Secrets | Kubernetes Secrets or Vault | Injected at runtime, never in Git |
| CI | GitHub Actions | ruff, pytest, golangci-lint, Docker build |

---

## Environment Variables

The full list lives in `.env.example`. The categories:

- Postgres connection string for SQLAlchemy
- Django secret key, debug flag, allowed hosts
- Redis URL, which serves all three Redis roles from one instance
- Kafka bootstrap servers and topic names for findings, events, and stats
- gRPC address for the Go service
- JWT signing key and token lifetimes, OAuth2 client credentials
- CORS allowed origins for the frontend
- Datadog service name, environment, agent host, and feature toggles for traces, metrics, and log injection

---

## Reading Order

Start with this file for the shape of the system. Read DESIGN.md to understand why each choice was made and what was rejected. Use LAYOUT.md as a reference while building. Follow PHASES.md in order — each phase produces something runnable and builds on the last. Reach for INFRA.md when you deploy and OPERATIONS.md when you are on call.

---

## Contributing

This is a learning project. The bar for any change: it should leave the system more observable, more reliable, or more secure than you found it.

---

## License

Learning project — do whatever you want with it.
