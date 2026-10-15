

Device Manager — Architecture Walkthrough

1. The Mental Model

Before components, here's the one idea the whole thing rests on:

Current state and event history are different problems, and they need different tools.

- Current state — "what devices are on my network right now" — is a relational query. Postgres owns it.
- Event history — "what was observed, when, by which scanner, in what order, replayably" — is a log problem. Kafka owns it.

Everything else in the architecture is a consequence of holding both. The cache exists because reading current state is hot. The queue exists because discovering devices is slow. The WebSocket exists because nobody wants to refresh a page. The Go service exists because scanning a network is a systems-level job. The auth layer exists because the API is exposed. Each component answers one question, and each one is independently deployable, scalable, and failure-isolated.

┌─────────────────────────────────────────────────────────────┐
│  EDGE          Nginx (TLS, WS proxy, static)                 │
├─────────────────────────────────────────────────────────────┤
│  COMPUTE       DRF (stateless HTTP)                          │
│                Channels ASGI (stateful WS holder)            │
│                Celery (async work)                           │
│                nettrace/Go (network scan)                    │
│                Faust (stream aggregation)                    │
├─────────────────────────────────────────────────────────────┤
│  DATA          Postgres (state) · Kafka (history)            │
│                Redis (cache + broker + pubsub)               │
├─────────────────────────────────────────────────────────────┤
│  CROSS-CUT     Keycloak (auth) · Datadog (observability)     │
│                Vault (secrets) · cert-manager (mTLS)         │
├─────────────────────────────────────────────────────────────┤
│  DELIVERY      Terraform (substrate) · Helm (workloads)      │
└─────────────────────────────────────────────────────────────┘

---

2. Design Patterns Used

Not patterns as decoration — each one solves a specific seam in this system.

┌─────┬─────────────────────────────────────────┬────────────────────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  #  │                 Pattern                 │                           Where it lives                           │                                              The problem it solves                                              │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 1   │ Layered / DDD                           │ domain/ pure, infrastructure/ side-effects                         │ Business rules testable with zero DB, network, or container. Swap Postgres for DynamoDB without touching        │
│     │                                         │                                                                    │ domain.                                                                                                         │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 2   │ Ports & Adapters                        │ Repository ABC in domain, SQLAlchemy/Caching/InMemory impls        │ The domain declares what it needs; the outside world provides it. Direction of dependency is enforced.          │
│     │                                         │ outside                                                            │                                                                                                                 │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 3   │ Repository                              │ DeviceRepository interface + 3 implementations                     │ Same service code runs against a dict, Postgres, or Postgres+cache. Tests never need a database.                │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 4   │ Strategy                                │ VendorLookup (InMemory / Postgres)                                 │ MAC→vendor source is swappable at startup without touching callers.                                             │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 5   │ Unit of Work                            │ One session per operation, commit-on-success / rollback-on-failure │ DB state stays consistent within a use case; no half-written devices.                                           │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 6   │ Decorator                               │ CachingDeviceRepository wraps any DeviceRepository                 │ Adds caching without modifying the wrapped repo. Composes: Postgres → cache → (later) metrics.                  │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 7   │ Dependency Injection                    │ Service constructors take interfaces, never concrete classes       │ The wiring happens once at startup; everything downstream is testable.                                          │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 8   │ Pub / Sub                               │ Redis for in-process, Kafka for cross-service                      │ Producers don't know how many consumers exist. Add a consumer without touching the producer.                    │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 9   │ Circuit Breaker (light)                 │ Cache falls through to DB when Redis is down                       │ Reads degrade, they don't crash.                                                                                │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 10  │ 202 Accepted + Task Queue               │ POST /api/trace/ → Celery → poll/push                              │ Decouples accepting work from doing work. HTTP worker freed in milliseconds.                                    │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 11  │ Streams–Table Join                      │ Faust tumbling window materialized into Postgres                   │ "New devices per minute" computed incrementally, not by scanning the log on every chart render.                 │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 12  │ Resource Server (OAuth2)                │ DRF and Go service validate JWTs against Keycloak's public key     │ Neither service ever handles a password. Revoke in one place, access dies everywhere.                           │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 13  │ Idempotent Consumer                     │ (mac, observed_at, source) key + commit-offset-after-write         │ Redelivery is safe. Crash between DB write and offset commit → duplicate absorbed.                              │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 14  │ Value Object vs Entity                  │ DeviceFinding frozen, Device mutable                               │ Historical fact can't be mutated; current state can. The type system enforces the distinction.                  │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 15  │ Health Check (liveness/readiness split) │ Two probes per deployment                                          │ Restart only when wedged; stop routing only when unable to serve. Confusing them causes cascading outages.      │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 16  │ Graceful Degradation                    │ Every external dependency has a fallback path                      │ System gets less useful, never more broken, as components fail.                                                 │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 17  │ Edge Termination                        │ TLS at Nginx, plain HTTP internally                                │ Add/remove app replicas without touching certificate config.                                                    │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 18  │ Infrastructure as Code /                │ Terraform + Helm + monitoring-as-code                              │ Cluster, DNS, certs, and alerting rules are all reviewed like code.                                             │
│     │ GitOps-adjacent                         │                                                                    │                                                                                                                 │
└─────┴─────────────────────────────────────────┴────────────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

The three that matter most to internalize: Layered/DDD (makes everything else testable), Pub/Sub via Kafka (makes the system extensible), and 202+Queue (makes the API responsive under slow work). If you only take three things from this project, take those.

---

3. What You Actually Gain

Languages & runtimes

- Python async — async/await end to end, SQLAlchemy 2.0 async engine, async Redis, async Channels
- Go — modules, goroutines + WaitGroups for parallel I/O, gRPC servers with streaming, reading /proc/net/arp, mDNS multicast, NetBIOS
- JavaScript — React hooks, WebSocket client lifecycle, reconnection backoff

Data & messaging

- Apache Avro — schema design, nullable unions, logical timestamps, schema evolution rules (forward/backward compatibility), why binary beats JSON at volume
- Apache Kafka — topics, partitions, consumer groups, offsets, retention, KRaft mode, acks/linger/compression tuning, consumer lag, replay, rebalancing
- Kafka Streams / Faust — tumbling windows, state stores, changelog topics, the Streams–Table-Join pattern (transfers directly to Java Kafka Streams and Flink)
- Redis used three ways — cache-aside with TTL, broker queue (durable), pub/sub (ephemeral) — and why each needs different persistence config
- PostgreSQL — async driver, indexing strategy, append-only event tables, monthly partitioning, Alembic migrations

Web & API

- Django REST Framework — ViewSets, serializers, cursor vs offset pagination, permission classes as the enforcement point, CORS
- ASGI / Django Channels — why ASGI not WSGI, ProtocolTypeRouter, WebSocket consumers, group messaging, the sync↔async bridge
- JWT + OAuth2 — token structure, RS256 vs HS256, JWKS, resource-server pattern, scopes, refresh flow
- Nginx — TLS termination, SPA routing fallback, the exact headers required to proxy a WebSocket upgrade

Observability

- Distributed tracing — one trace_id stitching DRF → Celery → Go → Kafka → Postgres into one flame graph, propagated through Kafka message headers
- Structured logging — JSON logs as queryable data, not grep targets
- SLOs — expressing health as a number with a threshold and an owner
- Custom metrics — counters vs gauges, consumer lag, cache hit rate

Operations

- Kubernetes — Deployment vs StatefulSet, Services, PVC, HPA, PDB, NetworkPolicy, probes, graceful shutdown
- Helm — one chart, many values files, subcharts, templating
- Terraform — modules, state, plan/apply, monitoring-as-code
- mTLS — certificate chains, SANs, client auth, what a service mesh automates
- Backup/restore — logical dumps, deduplicating storage, retention, rehearsed restores
- Runbooks — every alert has a documented response

Core understanding (the transferable part)

1. Current state and event history are different problems — and conflating them is the root of most bad architectures
2. The queue is what makes an API responsive — accept fast, process slow
3. A producer should not know its consumers — that's what makes a system extensible
4. Observability is what separates senior from junior — more than any framework or language
5. Failure design beats happy-path design — a system's quality is measured by how it degrades
6. Each component's scaling rule is different — and using the wrong trigger wastes money or fails to help

---

4. Path Walkthroughs — What Gets Touched, In Order

Path A — POST /api/trace/ (the main write path, the one to memorize)

Browser ──▶ Nginx ──▶ DRF ──▶ Celery ──▶ nettrace(Go) ──▶ Kafka ──▶ Consumers ──▶ Postgres
                │                                                        │
                │                                                        └──▶ Redis pubsub ──▶ ASGI ──▶ Browser

Synchronous part (milliseconds):
1. Browser sends POST /api/trace/ with the JWT in the Authorization header.
2. Nginx terminates TLS, proxies to the DRF Service.
3. Uvicorn/ASGI routes to Django middleware → DRF.
4. DRF authentication validates the JWT signature against Keycloak's JWKS public key. No session lookup — stateless.
5. DRF permission checks the token's scope claim contains trace:execute. If not → 403 here, before any business logic runs.
6. Serializer validates the subnet is a well-formed CIDR. If not → 400.
7. TraceViewSet enqueues a Celery task onto the Redis broker queue and returns 202 Accepted with a task_id.
8. Browser now polls GET /api/trace/{task_id}/ or waits for a WebSocket push.

Asynchronous part (seconds):
9. Celery worker does a blocking-pop on the Redis broker queue and picks up the task.
10. TraceCoordinator (application layer) calls the Go service over mTLS gRPC.
11. nettrace (Go) runs three scanners in parallel goroutines — ARP cache read, mDNS multicast, NetBIOS name queries — then merges results by MAC, preferring the most recent observation. A context timeout bounds the whole thing.
12. For each finding, nettrace Avro-encodes it and produces to Kafka topic device-findings, keyed by MAC (so all observations of one device land on one partition, in order).
13. Kafka appends to the partition's log and returns an ack.

Now three consumers read the same messages independently:
14. Ingestion consumer (own consumer group) decodes Avro → calls DeviceService.ingest():
    - CachingDeviceRepository.get_by_mac() → Redis miss → SQLAlchemyDeviceRepository → SELECT
    - New device? INSERT into devices + append to device_events. Existing? UPDATE + append.
    - Commit the DB transaction.
    - Only now commit the Kafka offset (this ordering is what makes redelivery safe).
    - Invalidate the Redis cache keys for that device and the recent list.
    - Publish DeviceUpdated to the Redis pub/sub channel ws-events.
15. Faust stream processor (own group) updates its tumbling window of new-devices-per-minute and materializes the result into a Postgres stats table.
16. Metrics consumer (own group) counts findings by vendor and emits a Datadog gauge. Writes nothing.

The push back to the browser:
17. ASGI/Channels worker is subscribed to ws-events. It receives the publish and does a group_send to the devices group.
18. Every DeviceConsumer in that group calls send_json → WebSocket frame → browser.
19. React upserts the device into the table, raises a toast if it's new, advances the timeline chart.

Woven through all of it: every hop (2, 4, 7, 9, 11, 12, 14, 17) emits a span tagged with subnet, task_id, user_id. The trace ID propagates from the HTTP header into the Celery task into the Kafka message headers, so the entire journey is one flame graph in Datadog. When the dashboard shows 0 devices, you open that one trace and see exactly which hop failed.

---

Path B — GET /api/devices/ (the cached read path)

1. Browser → Nginx → DRF → JWT auth → scope check (device:read).
2. DevicesViewSet.list() → DeviceService.list_recent().
3. CachingDeviceRepository.get_recent() checks Redis key devices:recent:25:
   - HIT → return immediately. Sub-millisecond. Postgres never touched.
   - MISS → fall through to SQLAlchemyDeviceRepository → SELECT ... ORDER BY last_seen DESC LIMIT 25 → write result to Redis with a TTL → return.
4. DRF applies offset pagination + serializes → JSON → Nginx → browser.

The invalidation tie-in: Path A step 14 deletes devices:recent:25 when it writes a device. So the next read misses and repopulates with fresh data. Cache-aside with write-through invalidation. Without that delete, the dashboard would show stale IPs for up to the TTL.

---

Path C — WebSocket lifecycle (how the push in Path A actually arrives)

1. Browser opens new WebSocket(wss://host/ws/?token=<jwt>) — token in the query param because browsers can't set headers on a WS upgrade.
2. Nginx sees the Upgrade header and proxies with Connection: upgrade. Without those two headers the handshake fails — this is the single most common WS misconfiguration.
3. ASGI ProtocolTypeRouter routes the WebSocket (not HTTP) protocol to the consumer stack.
4. AuthMiddlewareStack validates the JWT from the query string. Anonymous → reject.
5. DeviceConsumer.connect() accepts, then group_add("devices", channel_name).
6. Connection idles, held by the ASGI process — not by Nginx, not by the HTTP handler.
7. When Path A step 14 publishes to Redis, the Channels Redis layer delivers it to every ASGI worker subscribed, which calls device_updated on each consumer in the group → send_json → browser.
8. On drop, the browser's useWebSocket hook reconnects with exponential backoff (1s, 2s, 4s… capped at 30s).

Why this is a separate deployment from DRF: the HTTP handler is stateless and scales on CPU. The WS holder is stateful — each replica owns its connections — so it runs a fixed replica count, a PodDisruptionBudget (maxUnavailable: 0), and a long termination grace period so a rolling deploy never drops everyone at once.

---

Path D — A failure path: Redis cache goes down

1. GET /api/devices/ → CachingDeviceRepository.get_recent() → Redis GET throws a connection error.
2. The decorator catches it, logs a structured warning (redis_unavailable), and falls through to the SQLAlchemy repo.
3. The user gets their data from Postgres — ~3ms instead of <1ms. They notice nothing except a slightly slower page.
4. A redis_unavailable metric increments → eventually alerts.

That's graceful degradation: the system got less fast, not more broken. Every external dependency has a path like this.

---

Path E — A failure path: Kafka goes down during a trace

1. Celery picks up the trace task, nettrace scans successfully, tries to produce to Kafka → broker unreachable.
2. TraceCoordinator catches it and falls back to direct ingest: calls DeviceService.ingest() synchronously, writes to Postgres, publishes to Redis pub/sub anyway.
3. The dashboard still updates. Findings are persisted. The only loss is that those findings didn't travel through the event log, so the Faust window and metrics consumer missed them.
4. A trace_fallback metric increments → alerts.

The tradeoff is deliberate: availability of the write path over completeness of the event log. For device discovery, a brief gap in the aggregation is acceptable; a failed trace is not. A senior makes that tradeoff explicitly and instruments it; a junior either doesn't notice or picks the opposite and loses data during a broker blip.

---

The One Paragraph to Remember

A trace click becomes an HTTP request that accepts work and returns immediately; a Celery worker performs it by asking a Go service to scan the network; findings travel as Avro over Kafka so that multiple consumers can process the same event for different purposes without the producer knowing they exist; the ingestion consumer writes to Postgres as the source of truth, commits its offset only after the write succeeds so redelivery is safe, and publishes to Redis pub/sub; the ASGI worker pushes to the browser over a WebSocket; and every hop emits a span so the whole journey is one traceable, debuggable, alertable unit. Each piece exists because removing it would break one of: responsiveness, durability, extensibility, freshness, or observability.

Want me to go deeper on any single path — for example, exactly what happens during a Kafka consumer group rebalance, or how the Faust window state survives a restart?



Device Manager — Architecture Walkthrough

1. The Mental Model

Before components, here's the one idea the whole thing rests on:

Current state and event history are different problems, and they need different tools.

- Current state — "what devices are on my network right now" — is a relational query. Postgres owns it.
- Event history — "what was observed, when, by which scanner, in what order, replayably" — is a log problem. Kafka owns it.

Everything else in the architecture is a consequence of holding both. The cache exists because reading current state is hot. The queue exists because discovering devices is slow. The WebSocket exists because nobody wants to refresh a page. The Go service exists because scanning a network is a systems-level job. The auth layer exists because the API is exposed. Each component answers one question, and each one is independently deployable, scalable, and failure-isolated.

┌─────────────────────────────────────────────────────────────┐
│  EDGE          Nginx (TLS, WS proxy, static)                 │
├─────────────────────────────────────────────────────────────┤
│  COMPUTE       DRF (stateless HTTP)                          │
│                Channels ASGI (stateful WS holder)            │
│                Celery (async work)                           │
│                nettrace/Go (network scan)                    │
│                Faust (stream aggregation)                    │
├─────────────────────────────────────────────────────────────┤
│  DATA          Postgres (state) · Kafka (history)            │
│                Redis (cache + broker + pubsub)               │
├─────────────────────────────────────────────────────────────┤
│  CROSS-CUT     Keycloak (auth) · Datadog (observability)     │
│                Vault (secrets) · cert-manager (mTLS)         │
├─────────────────────────────────────────────────────────────┤
│  DELIVERY      Terraform (substrate) · Helm (workloads)      │
└─────────────────────────────────────────────────────────────┘

---

2. Design Patterns Used

Not patterns as decoration — each one solves a specific seam in this system.

┌─────┬─────────────────────────────────────────┬────────────────────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  #  │                 Pattern                 │                           Where it lives                           │                                              The problem it solves                                              │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 1   │ Layered / DDD                           │ domain/ pure, infrastructure/ side-effects                         │ Business rules testable with zero DB, network, or container. Swap Postgres for DynamoDB without touching        │
│     │                                         │                                                                    │ domain.                                                                                                         │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 2   │ Ports & Adapters                        │ Repository ABC in domain, SQLAlchemy/Caching/InMemory impls        │ The domain declares what it needs; the outside world provides it. Direction of dependency is enforced.          │
│     │                                         │ outside                                                            │                                                                                                                 │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 3   │ Repository                              │ DeviceRepository interface + 3 implementations                     │ Same service code runs against a dict, Postgres, or Postgres+cache. Tests never need a database.                │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 4   │ Strategy                                │ VendorLookup (InMemory / Postgres)                                 │ MAC→vendor source is swappable at startup without touching callers.                                             │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 5   │ Unit of Work                            │ One session per operation, commit-on-success / rollback-on-failure │ DB state stays consistent within a use case; no half-written devices.                                           │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 6   │ Decorator                               │ CachingDeviceRepository wraps any DeviceRepository                 │ Adds caching without modifying the wrapped repo. Composes: Postgres → cache → (later) metrics.                  │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 7   │ Dependency Injection                    │ Service constructors take interfaces, never concrete classes       │ The wiring happens once at startup; everything downstream is testable.                                          │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 8   │ Pub / Sub                               │ Redis for in-process, Kafka for cross-service                      │ Producers don't know how many consumers exist. Add a consumer without touching the producer.                    │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 9   │ Circuit Breaker (light)                 │ Cache falls through to DB when Redis is down                       │ Reads degrade, they don't crash.                                                                                │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 10  │ 202 Accepted + Task Queue               │ POST /api/trace/ → Celery → poll/push                              │ Decouples accepting work from doing work. HTTP worker freed in milliseconds.                                    │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 11  │ Streams–Table Join                      │ Faust tumbling window materialized into Postgres                   │ "New devices per minute" computed incrementally, not by scanning the log on every chart render.                 │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 12  │ Resource Server (OAuth2)                │ DRF and Go service validate JWTs against Keycloak's public key     │ Neither service ever handles a password. Revoke in one place, access dies everywhere.                           │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 13  │ Idempotent Consumer                     │ (mac, observed_at, source) key + commit-offset-after-write         │ Redelivery is safe. Crash between DB write and offset commit → duplicate absorbed.                              │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 14  │ Value Object vs Entity                  │ DeviceFinding frozen, Device mutable                               │ Historical fact can't be mutated; current state can. The type system enforces the distinction.                  │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 15  │ Health Check (liveness/readiness split) │ Two probes per deployment                                          │ Restart only when wedged; stop routing only when unable to serve. Confusing them causes cascading outages.      │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 16  │ Graceful Degradation                    │ Every external dependency has a fallback path                      │ System gets less useful, never more broken, as components fail.                                                 │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 17  │ Edge Termination                        │ TLS at Nginx, plain HTTP internally                                │ Add/remove app replicas without touching certificate config.                                                    │
├─────┼─────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 18  │ Infrastructure as Code /                │ Terraform + Helm + monitoring-as-code                              │ Cluster, DNS, certs, and alerting rules are all reviewed like code.                                             │
│     │ GitOps-adjacent                         │                                                                    │                                                                                                                 │
└─────┴─────────────────────────────────────────┴────────────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

The three that matter most to internalize: Layered/DDD (makes everything else testable), Pub/Sub via Kafka (makes the system extensible), and 202+Queue (makes the API responsive under slow work). If you only take three things from this project, take those.

---

3. What You Actually Gain

Languages & runtimes

- Python async — async/await end to end, SQLAlchemy 2.0 async engine, async Redis, async Channels
- Go — modules, goroutines + WaitGroups for parallel I/O, gRPC servers with streaming, reading /proc/net/arp, mDNS multicast, NetBIOS
- JavaScript — React hooks, WebSocket client lifecycle, reconnection backoff

Data & messaging

- Apache Avro — schema design, nullable unions, logical timestamps, schema evolution rules (forward/backward compatibility), why binary beats JSON at volume
- Apache Kafka — topics, partitions, consumer groups, offsets, retention, KRaft mode, acks/linger/compression tuning, consumer lag, replay, rebalancing
- Kafka Streams / Faust — tumbling windows, state stores, changelog topics, the Streams–Table-Join pattern (transfers directly to Java Kafka Streams and Flink)
- Redis used three ways — cache-aside with TTL, broker queue (durable), pub/sub (ephemeral) — and why each needs different persistence config
- PostgreSQL — async driver, indexing strategy, append-only event tables, monthly partitioning, Alembic migrations

Web & API

- Django REST Framework — ViewSets, serializers, cursor vs offset pagination, permission classes as the enforcement point, CORS
- ASGI / Django Channels — why ASGI not WSGI, ProtocolTypeRouter, WebSocket consumers, group messaging, the sync↔async bridge
- JWT + OAuth2 — token structure, RS256 vs HS256, JWKS, resource-server pattern, scopes, refresh flow
- Nginx — TLS termination, SPA routing fallback, the exact headers required to proxy a WebSocket upgrade

Observability

- Distributed tracing — one trace_id stitching DRF → Celery → Go → Kafka → Postgres into one flame graph, propagated through Kafka message headers
- Structured logging — JSON logs as queryable data, not grep targets
- SLOs — expressing health as a number with a threshold and an owner
- Custom metrics — counters vs gauges, consumer lag, cache hit rate

Operations

- Kubernetes — Deployment vs StatefulSet, Services, PVC, HPA, PDB, NetworkPolicy, probes, graceful shutdown
- Helm — one chart, many values files, subcharts, templating
- Terraform — modules, state, plan/apply, monitoring-as-code
- mTLS — certificate chains, SANs, client auth, what a service mesh automates
- Backup/restore — logical dumps, deduplicating storage, retention, rehearsed restores
- Runbooks — every alert has a documented response

Core understanding (the transferable part)

1. Current state and event history are different problems — and conflating them is the root of most bad architectures
2. The queue is what makes an API responsive — accept fast, process slow
3. A producer should not know its consumers — that's what makes a system extensible
4. Observability is what separates senior from junior — more than any framework or language
5. Failure design beats happy-path design — a system's quality is measured by how it degrades
6. Each component's scaling rule is different — and using the wrong trigger wastes money or fails to help

---

4. Path Walkthroughs — What Gets Touched, In Order

Path A — POST /api/trace/ (the main write path, the one to memorize)

Browser ──▶ Nginx ──▶ DRF ──▶ Celery ──▶ nettrace(Go) ──▶ Kafka ──▶ Consumers ──▶ Postgres
                │                                                        │
                │                                                        └──▶ Redis pubsub ──▶ ASGI ──▶ Browser

Synchronous part (milliseconds):
1. Browser sends POST /api/trace/ with the JWT in the Authorization header.
2. Nginx terminates TLS, proxies to the DRF Service.
3. Uvicorn/ASGI routes to Django middleware → DRF.
4. DRF authentication validates the JWT signature against Keycloak's JWKS public key. No session lookup — stateless.
5. DRF permission checks the token's scope claim contains trace:execute. If not → 403 here, before any business logic runs.
6. Serializer validates the subnet is a well-formed CIDR. If not → 400.
7. TraceViewSet enqueues a Celery task onto the Redis broker queue and returns 202 Accepted with a task_id.
8. Browser now polls GET /api/trace/{task_id}/ or waits for a WebSocket push.

Asynchronous part (seconds):
9. Celery worker does a blocking-pop on the Redis broker queue and picks up the task.
10. TraceCoordinator (application layer) calls the Go service over mTLS gRPC.
11. nettrace (Go) runs three scanners in parallel goroutines — ARP cache read, mDNS multicast, NetBIOS name queries — then merges results by MAC, preferring the most recent observation. A context timeout bounds the whole thing.
12. For each finding, nettrace Avro-encodes it and produces to Kafka topic device-findings, keyed by MAC (so all observations of one device land on one partition, in order).
13. Kafka appends to the partition's log and returns an ack.

Now three consumers read the same messages independently:
14. Ingestion consumer (own consumer group) decodes Avro → calls DeviceService.ingest():
    - CachingDeviceRepository.get_by_mac() → Redis miss → SQLAlchemyDeviceRepository → SELECT
    - New device? INSERT into devices + append to device_events. Existing? UPDATE + append.
    - Commit the DB transaction.
    - Only now commit the Kafka offset (this ordering is what makes redelivery safe).
    - Invalidate the Redis cache keys for that device and the recent list.
    - Publish DeviceUpdated to the Redis pub/sub channel ws-events.
15. Faust stream processor (own group) updates its tumbling window of new-devices-per-minute and materializes the result into a Postgres stats table.
16. Metrics consumer (own group) counts findings by vendor and emits a Datadog gauge. Writes nothing.

The push back to the browser:
17. ASGI/Channels worker is subscribed to ws-events. It receives the publish and does a group_send to the devices group.
18. Every DeviceConsumer in that group calls send_json → WebSocket frame → browser.
19. React upserts the device into the table, raises a toast if it's new, advances the timeline chart.

Woven through all of it: every hop (2, 4, 7, 9, 11, 12, 14, 17) emits a span tagged with subnet, task_id, user_id. The trace ID propagates from the HTTP header into the Celery task into the Kafka message headers, so the entire journey is one flame graph in Datadog. When the dashboard shows 0 devices, you open that one trace and see exactly which hop failed.

---

Path B — GET /api/devices/ (the cached read path)

1. Browser → Nginx → DRF → JWT auth → scope check (device:read).
2. DevicesViewSet.list() → DeviceService.list_recent().
3. CachingDeviceRepository.get_recent() checks Redis key devices:recent:25:
   - HIT → return immediately. Sub-millisecond. Postgres never touched.
   - MISS → fall through to SQLAlchemyDeviceRepository → SELECT ... ORDER BY last_seen DESC LIMIT 25 → write result to Redis with a TTL → return.
4. DRF applies offset pagination + serializes → JSON → Nginx → browser.

The invalidation tie-in: Path A step 14 deletes devices:recent:25 when it writes a device. So the next read misses and repopulates with fresh data. Cache-aside with write-through invalidation. Without that delete, the dashboard would show stale IPs for up to the TTL.

---

Path C — WebSocket lifecycle (how the push in Path A actually arrives)

1. Browser opens new WebSocket(wss://host/ws/?token=<jwt>) — token in the query param because browsers can't set headers on a WS upgrade.
2. Nginx sees the Upgrade header and proxies with Connection: upgrade. Without those two headers the handshake fails — this is the single most common WS misconfiguration.
3. ASGI ProtocolTypeRouter routes the WebSocket (not HTTP) protocol to the consumer stack.
4. AuthMiddlewareStack validates the JWT from the query string. Anonymous → reject.
5. DeviceConsumer.connect() accepts, then group_add("devices", channel_name).
6. Connection idles, held by the ASGI process — not by Nginx, not by the HTTP handler.
7. When Path A step 14 publishes to Redis, the Channels Redis layer delivers it to every ASGI worker subscribed, which calls device_updated on each consumer in the group → send_json → browser.
8. On drop, the browser's useWebSocket hook reconnects with exponential backoff (1s, 2s, 4s… capped at 30s).

Why this is a separate deployment from DRF: the HTTP handler is stateless and scales on CPU. The WS holder is stateful — each replica owns its connections — so it runs a fixed replica count, a PodDisruptionBudget (maxUnavailable: 0), and a long termination grace period so a rolling deploy never drops everyone at once.

---

Path D — A failure path: Redis cache goes down

1. GET /api/devices/ → CachingDeviceRepository.get_recent() → Redis GET throws a connection error.
2. The decorator catches it, logs a structured warning (redis_unavailable), and falls through to the SQLAlchemy repo.
3. The user gets their data from Postgres — ~3ms instead of <1ms. They notice nothing except a slightly slower page.
4. A redis_unavailable metric increments → eventually alerts.

That's graceful degradation: the system got less fast, not more broken. Every external dependency has a path like this.

---

Path E — A failure path: Kafka goes down during a trace

1. Celery picks up the trace task, nettrace scans successfully, tries to produce to Kafka → broker unreachable.
2. TraceCoordinator catches it and falls back to direct ingest: calls DeviceService.ingest() synchronously, writes to Postgres, publishes to Redis pub/sub anyway.
3. The dashboard still updates. Findings are persisted. The only loss is that those findings didn't travel through the event log, so the Faust window and metrics consumer missed them.
4. A trace_fallback metric increments → alerts.

The tradeoff is deliberate: availability of the write path over completeness of the event log. For device discovery, a brief gap in the aggregation is acceptable; a failed trace is not. A senior makes that tradeoff explicitly and instruments it; a junior either doesn't notice or picks the opposite and loses data during a broker blip.

---

The One Paragraph to Remember

A trace click becomes an HTTP request that accepts work and returns immediately; a Celery worker performs it by asking a Go service to scan the network; findings travel as Avro over Kafka so that multiple consumers can process the same event for different purposes without the producer knowing they exist; the ingestion consumer writes to Postgres as the source of truth, commits its offset only after the write succeeds so redelivery is safe, and publishes to Redis pub/sub; the ASGI worker pushes to the browser over a WebSocket; and every hop emits a span so the whole journey is one traceable, debuggable, alertable unit. Each piece exists because removing it would break one of: responsiveness, durability, extensibility, freshness, or observability.

Want me to go deeper on any single path — for example, exactly what happens during a Kafka consumer group rebalance, or how the Faust window state survives a restart?

✻ Sautéed for 1m 15s · done 10:02 AM

❯  how the Faust window state survives - what is a faust window? also is the above clear explanation saved as a file anywahere on disk?

  Thought for 1m 30s

Good questions — let me answer the Faust one properly, then deal with the file.

What a window is

A Kafka topic is infinite. You cannot run COUNT(*) GROUP BY minute over an infinite stream, because there is no "last minute" — events keep arriving. A window is how you chop the unbounded stream into bounded buckets so aggregation becomes possible.

Faust has three kinds:

┌──────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────┬────────────────────────────────────────────────────┐
│  Window  │                                                  Behavior                                                  │                      Use case                      │
├──────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
│ Tumbling │ Fixed size, non-overlapping. 10:00–10:01, then 10:01–10:02, with no gap and no overlap.                    │ "New devices per minute" — calendar-minute buckets │
├──────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
│ Hopping  │ Fixed size, overlapping. A 5-minute window that advances every 1 minute, so each event lands in 5 windows. │ Smoothing noisy metrics                            │
├──────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
│ Sliding  │ Event-driven, not clock-driven. Two events share a window if they're within X of each other.               │ Sessionization — "a burst of activity"             │
└──────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────┴────────────────────────────────────────────────────┘

This project uses tumbling for the timeline chart. The minute bucket closes, gets materialized into Postgres, and the chart reads the materialized table instead of scanning the raw event log.

How the state survives a restart

The key insight: the window state is not just in memory. It lives in three places with three survival profiles.

┌───────────────────────┬──────────────────────────┬────────────────────┬────────────────────────┐
│         Layer         │ Survives process restart │ Survives node loss │ Survives cluster loss  │
├───────────────────────┼──────────────────────────┼────────────────────┼────────────────────────┤
│ In-memory dict        │ No                       │ No                 │ No                     │
├───────────────────────┼──────────────────────────┼────────────────────┼────────────────────────┤
│ RocksDB on local disk │ Yes                      │ No                 │ No                     │
├───────────────────────┼──────────────────────────┼────────────────────┼────────────────────────┤
│ Kafka changelog topic │ Yes                      │ Yes                │ Yes (with replication) │
└───────────────────────┴──────────────────────────┴────────────────────┴────────────────────────┘

RocksDB is an embedded on-disk key-value store (Facebook's fork of LevelDB). Faust uses it as the state store — so window contents are written to local disk, not held only in RAM.

The changelog topic is the important one. Every write to a Faust table also goes to a dedicated compacted Kafka topic — compaction means Kafka keeps the latest value per key forever, not "delete after 7 days." So the changelog is a durable, replayable record of the window's state.

The restart sequence

Shutdown:
1. Faust receives SIGTERM
2. Stops consuming new input messages
3. Flushes the current window state to RocksDB and ensures the changelog topic reflects it
4. Exits cleanly

Startup:
1. New worker subscribes to the changelog topic
2. Restores — reads the changelog and rebuilds RocksDB/memory until caught up
3. Only then starts consuming the input topic from its committed offset
4. Resumes processing with full window state

The payoff, and why it matters architecturally

Because the authoritative state is in Kafka, a Faust worker can move to a different node and restore from the changelog. That is what makes the stream processor behave like a stateless deployment even though it holds windowed state. Kafka Streams (Java) and Flink use exactly this mechanism — learning it here transfers directly.

The honest nuance a senior knows

The crash window between "write state" and "commit offset" creates an at-least-once replay. If the worker dies after counting event 4 but before committing the offset, it restores count=4 and then replays event 1 — and a naive counter now says 5.

Two ways this project handles it:

1. Store a set of MACs, not a count. The window's value is the set of distinct MACs seen in that minute. Redelivering a MAC that's already in the set is a no-op. The count is len(set) at materialization time. This is the clean fix.
2. The idempotency key (mac, observed_at, source) from the ingestion layer — but note the Faust consumer is a separate consumer group with its own offsets, so it needs its own dedup reasoning, not the ingestion layer's.

Option 1 is what I'd build. It's the same reasoning that makes the ingestion consumer safe, applied at the aggregation layer.

---

Is the walkthrough saved?

No. Last turn's explanation lived only in this conversation — the six files on disk are README.md, DESIGN.md, LAYOUT.md, PHASES.md, INFRA.md, and OPERATIONS.md. The architecture walkthrough, the design-patterns table, and the path traces (A through E) were never written to disk, so they'd be lost if this session ended.

Let me save them now, along with the window explanation.

● Write(ARCHITECTURE.md)
Wrote 272 lines to ARCHITECTURE.md
# Architecture — Patterns, Components, and Path Walkthroughs

This file is the connective tissue between the design decisions and the folder layout. It names every design pattern in use, states what each one solves, maps the technology surface to what you gain from it, and then walks
the actual request paths end to end so you can see which components are touched and in what order.

Read README.md first for the shape of the system, DESIGN.md for why the choices were made, and this file when you want to trace a request.

---

## The Mental Model
… +276 lines

Now let me add it to the README's docs table so the set stays discoverable.

● Update(README.md)
Added 1 line
| File | Contents |
|---|---|
| README.md | This file. Overview, topology, the junior/senior framing, tech stack, env vars |
| ARCHITECTURE.md | Design patterns used, what you gain from each technology, and end-to-end request path walkthroughs (trace, read, WebSocket, failure paths, Faust windows) |
| DESIGN.md | Every architectural decision, why it was made, what alternatives were rejected |
| LAYOUT.md | Folder-by-folder map, what goes where, import rules, how it maps to production |
| PHASES.md | Build order, zero to fourteen, each with goals, learning, and acceptance criteria |

Saved. Here's the answer to both questions:

Faust windows, short version

A Kafka topic is infinite, so you cannot run COUNT(*) GROUP BY minute over it — there is no "last minute," events keep arriving. A window chops the unbounded stream into bounded buckets so aggregation is possible. The project uses tumbling windows (fixed, non-overlapping, 10:00–10:01 then 10:01–10:02) for the timeline chart.

Window state survives in three layers: in-memory dict (survives nothing), RocksDB on local disk (survives process restart), and a compacted Kafka changelog topic (survives node loss). On restart, Faust restores from the changelog before resuming consumption, which is what lets it move nodes and still behave statelessly. That mechanism is the same one Kafka Streams and Flink use.

The senior nuance is in the file: because replay is at-least-once, a naive counter double-counts after a crash. The fix is storing a set of MACs per window rather than a count — redelivering a known MAC is a no-op.

Files on disk

You had seven, now you have seven — the walkthrough is now the seventh:

┌─────────────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│      File       │                                                          What's in it                                                          │
├─────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ README.md       │ Overview, topology diagram, junior/senior framing, env vars                                                                    │
├─────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ARCHITECTURE.md │ NEW — 18 design patterns, the "what you gain" technology map, and Paths A–E traced end to end, plus the Faust window deep dive │
├─────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ DESIGN.md       │ 18 decisions with rejected alternatives                                                                                        │
├─────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYOUT.md       │ Folder map, import rules, folder→deployment mapping                                                                            │
├─────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASES.md       │ Build order 0→14 with acceptance criteria                                                                                      │
├─────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ INFRA.md        │ Compose → manifests → Helm → Terraform                                                                                         │
├─────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ OPERATIONS.md   │ Health checks, shutdown, scaling, backups, runbooks                                                                            │
└─────────────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

The only content from last turn that didn't get saved verbatim was the closing one-paragraph summary and the offer to go deeper on consumer-group rebalancing — the substance of everything else, including the five paths and the window explanation, is now in ARCHITECTURE.md and referenced from the README's docs table.

✻ Sautéed for 1m 51s · done 10:52 AM

※ recap: Goal: document the device-manager project so it teaches production architecture. Seven design docs are written on disk, including ARCHITECTURE.md with the pattern list and request-path walkthroughs. Next: start building Phase 0, the project skeleton with uv and ruff config. (disable recaps in /config)

──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
❯
──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  ⏵⏵ auto mode on (shift+tab to cycle) · install gh for PR status · ← for agents5