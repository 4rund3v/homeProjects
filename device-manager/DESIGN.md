# Design Decisions — Device Manager

This file explains why every major architectural choice was made and what alternatives were considered. It is the rationale behind the folder structure, the dependency choices, and the patterns described in the README. Read it before building so the seams make sense when you hit them.

---

## 1. Layered / DDD-style Architecture

**Decision:** Four layers, cleanly separated by folder and enforced by convention: Domain, Application, Infrastructure, and Infrastructure-Web.

**Why:**
- Business logic stays free of framework imports. The domain layer cannot accidentally import SQLAlchemy or Django.
- Tests for domain logic run without a database, a network, or a container. This is the same model as clean/hexagonal architecture in Java Spring or C#.
- Each layer depends only inward. Infrastructure depends on the interfaces defined in Domain, never the reverse.

**Alternatives rejected:**
- Django-style fat models with logic in models.py — couples business rules to the ORM and to Django's request lifecycle, so you cannot test a rule without standing up Django.
- Service objects scattered in a top-level services.py — makes it impossible to tell an entrypoint from an orchestrator, and the file becomes a junk drawer.
- A single flat package — fine for a script, collapses under its own weight once you have real use cases.

**The payoff, concretely:** when you switch from Postgres to DynamoDB, only the infrastructure repositories change. The domain tests still pass untouched. That is the return on the discipline, and it only materializes if you enforce it from day one.

---

## 2. Repository Pattern

**Decision:** Each aggregate has a repository interface in the domain layer and multiple implementations in infrastructure. The application service accepts the interface, never a concrete class.

**Why:**
- Tests swap in an in-memory fake. The use case does not know whether it is running against Postgres, Postgres-plus-cache, or a dict.
- The interface is a standard-library ABC — no dependency-injection framework needed to learn the pattern.

**Alternatives rejected:**
- Passing the SQLAlchemy session directly into services — bakes one persistence choice into business logic, and every test needs a database.
- A DI container such as dependency-injector — rejected for learning purposes. Explicit constructor injection is clearer when the pattern is the thing being learned.

---

## 3. Strategy Pattern for Vendor Lookup

**Decision:** VendorLookup is an ABC with a single lookup method taking a MAC OUI prefix. Two implementations: an in-memory dict for tests and local dev, and a Postgres-backed lookup for real data. Selected at startup from configuration.

**Why:**
- MAC OUI to vendor name could come from a database, a CSV, or a network call. The strategy lets you swap the source without touching callers.
- It is a textbook GoF pattern, trivial to test, and easy to extend when you want a cached or remote variant.

**Alternatives rejected:**
- A hardcoded dictionary everywhere — fails the moment you need the full IEEE OUI database.
- A module-level function — no way to swap behavior per environment, no seam for tests.

---

## 4. Apache Avro as the Go-to-Python Wire Format

**Decision:** A binary Avro-encoded DeviceFinding is what the Go service produces and what Python decodes. One schema file drives both sides.

**Why:**
- Smaller than JSON. A single finding is tens of bytes versus a couple hundred for JSON, which matters when scanning thousands of devices per run.
- Schema evolution with a rule you can rely on: add a nullable field with a default and old consumers keep working. That is forward compatibility, and it is what lets you deploy a new field without coordinating a release across two languages.
- Cross-language. The same schema file is the contract for the Go encoder and the Python decoder.

**Alternatives rejected:**
- JSON over gRPC — simpler, but larger, no schema evolution, and no discipline. Someone will eventually rename a field and break a consumer silently.
- Protobuf — a perfectly valid choice. Avro was chosen because it is the Kafka ecosystem's native wire format and because the learning goal names it explicitly.
- FlatBuffers or Cap'n Proto — real advantages at extreme scale, overkill here.

**Timestamp precision:** the schema uses microsecond logical timestamps, not milliseconds. Three discovery mechanisms (ARP, mDNS, NetBIOS) can observe the same device within milliseconds of each other; microsecond precision preserves the ordering.

---

## 5. gRPC for Go-to-Python Communication

**Decision:** The nettrace binary exposes a TraceService gRPC service. The Celery worker calls it, not the HTTP handler.

**Why:**
- gRPC is the standard for polyglot RPC. Building the server in Go and the client in Python mirrors real mixed-language environments.
- The long-running server mode is the production deployment, called over mTLS. The one-shot CLI is the development convenience. Same binary, two modes.
- A streaming variant lets the Go service push findings as they are discovered instead of waiting for the whole scan. The consumer reads the stream and publishes each finding to Kafka as it arrives.

**Alternatives rejected:**
- Subprocess with stdout parsing — simpler, but fragile. No schema, no streaming, no retries, no mutual authentication.
- HTTP/JSON between services — works, but you would reach for gRPC in production for exactly this use case, so why learn the throwaway option.

**Keeping Avro and gRPC separate:** the Avro schema is the data contract for a finding. The proto is the RPC contract for calling the service. They evolve independently — you can add an RPC method without touching the Avro schema, and add an Avro field without regenerating stubs.

---

## 6. Kafka as the Durable Event Log

**Decision:** Findings are published to a Kafka topic keyed by MAC. Multiple consumer groups read independently. Postgres remains the source of truth for current state; Kafka is the transport and the history.

**Why:**
- Immutable, replayable log. If the aggregation logic has a bug, you reprocess history instead of mourning lost data.
- Producers and consumers are decoupled. The scanner does not know how many consumers exist. Adding a fourth consumer — alert on unknown MACs, feed a CMDB, export to a SIEM — requires no producer change.
- It teaches consumer groups, partitions, offsets, and the exactly-once ideas that underpin all data engineering.

**Alternatives rejected:**
- Redis Streams alone — simpler and lighter, but the replay story and the operational ecosystem are weaker. Redis Streams is used in addition for the in-process event path, not as a replacement.
- Celery broker only — a broker holds tasks, not a log. Wrong mental model for a history of observations.
- Writing straight to Postgres and polling — loses ordering, loses replay, and couples the scanner to the schema.

**Topic design:** findings keyed by MAC so observations of the same device stay ordered within a partition. A separate lower-volume topic for state-transition events (new device, vendor changed, device gone). A stats topic for the materialized aggregations. Retention tuned per topic — findings for a week, events for a day, stats for a month.

---

## 7. Kafka Streams / Faust for Windowed Aggregations

**Decision:** A Faust stream processor maintains a tumbling window of new devices per minute and a rolling window of devices per vendor, materialized into Postgres.

**Why:**
- Windowed aggregation is the signature Streams use case. It forces you to understand state stores, changelog topics, and window retention — concepts that transfer directly to the Java Kafka Streams API and to Flink.
- Faust is the canonical Python port, so you learn the pattern without leaving the language of the rest of the project.
- The materialized view is what the frontend timeline chart reads, so the chart never queries the raw event log.

**Alternatives rejected:**
- Computing the aggregation in SQL on read — fine functionally, but does not teach Streams, which is an explicit goal.
- Spark or Flink — far too heavy for a learning project on a laptop.

---

## 8. Redis for Three Distinct Roles

**Decision:** One Redis instance, three jobs, three different reliability profiles.

| Role | Pattern | Durability requirement |
|---|---|---|
| Device cache | Key/value with TTL | Ephemeral — a lost entry just means a database read |
| Celery broker | List operations | Durable — losing a queued task is losing work |
| Pub/sub for WebSocket events | Channel | Ephemeral — the next scan repopulates the dashboard |

**Why:**
- The cache cuts hot-read latency from a few milliseconds to sub-millisecond, with write-through invalidation on update.
- The broker queue is what decouples DRF from Celery. It must survive a restart, which means append-only file persistence in production.
- The pub/sub channel is the bridge between the Celery process (which publishes) and the ASGI process (which holds WebSocket connections). They are separate processes, so Redis is the transport between them.

**Why three roles coexist on one instance:** each uses a different region of the keyspace, and Redis is single-threaded per command but serves these workloads without contention. In production you would put Redis behind Sentinel or a Cluster for high availability, but the three roles still share one logical instance.

**Alternatives rejected:**
- Django's per-process in-memory cache — works single-process, breaks the moment you run more than one worker, and does not teach Redis.
- Redis only, no Kafka — you lose replayability and the decoupled consumer-group model.
- Pub/sub instead of a broker queue for Celery — a broker queue is durable until consumed; pub/sub is ephemeral and drops messages with no subscriber.

**The senior distinction here:** a junior sees "Redis" as one thing and enables snapshots and calls it done. When a restart loses queued tasks, they are surprised. A senior knows which persistence knob protects which role, and configures each accordingly.

---

## 9. PostgreSQL, PVC-backed

**Decision:** Postgres is the source of truth. Locally it runs in Docker Compose; on the cluster it runs as a StatefulSet with a PersistentVolumeClaim.

**Why:**
- Relational device data with a time-series event history is exactly what Postgres does well — unique key on MAC, indexed last_seen, indexed event timestamps.
- PVC-backed storage means device history survives cluster restarts. This is a real Kubernetes concept worth internalizing.
- asyncpg as the driver — faster than the synchronous driver under SQLAlchemy's async mode.

**Schema highlights:**
- devices — one row per device, keyed by MAC. Current IP, hostname, vendor, status, first and last seen.
- device_events — append-only observation log, indexed on device MAC and observed time. Partitioned by month once it grows.
- vendors — OUI prefix to vendor name, bulk-loaded from the IEEE registry.

**Alternatives rejected:**
- A time-series database such as TimescaleDB or InfluxDB — a reasonable choice at scale, rejected here because the relational auth and device-state data belongs in Postgres and splitting stores adds operational cost without teaching anything new at this scale.
- MongoDB — flexible schema is a liability here. The device shape is fixed and the integrity constraints are the point.

---

## 10. DRF as the HTTP API Layer

**Decision:** Django REST Framework ViewSets and routers for devices and events. A dedicated trace endpoint that enqueues work and returns 202.

**Why:**
- DRF gives serialization, validation, pagination, filtering, a browsable API, and a permission system for free. It is the standard Python API layer and the broadest-ecosystem pattern.
- The web layer contains zero business logic. It translates HTTP to application-service calls and back. That boundary is what keeps auth and validation auditable in one place.

**Alternatives rejected:**
- FastAPI — lighter and more modern, but DRF is more established for enterprise Python and teaches class-based views and serializers, which is the broader ecosystem pattern. The 202-and-poll flow works identically in either.
- Raw Django views — too much boilerplate for the same result.
- A separate microservice for the API — unjustified at this scale; the deployment boundary is DRF versus ASGI versus Celery, not a second web framework.

---

## 11. The Go Service (nettrace)

**Decision:** A single Cobra binary with two modes. One-shot CLI for development, long-running gRPC server for production.

**Why:**
- Network discovery is where Go earns its place. Reading the kernel ARP cache, sending mDNS multicast, and firing NetBIOS name queries are all better served by Go's networking primitives and goroutines than by Python under the GIL.
- Compiles to a static binary with no runtime dependency. Deployable as a container, a sidecar, or a process on a Raspberry Pi at the edge of the network.
- Cobra is the standard Go CLI framework, so the structure is familiar to anyone who has used kubectl or the Docker CLI.

**Discovery mechanisms, in order of reliability:**
- ARP table — read the kernel cache. No privileges needed, no packets sent, gives you the IP-to-MAC mappings already on the local link. This is the baseline.
- mDNS — multicast query for workstation and device-info records. Catches Apple devices, Linux machines with Avahi, many printers. Adds a few seconds because responses are asynchronous.
- NetBIOS — name query per address. Catches Windows hosts that ignore mDNS. Parallelized across the subnet because it is latency-bound.

The scanner runs all three in parallel and merges by MAC, preferring the most recent observation.

**Alternatives rejected:**
- Shelling out to nmap or arp-scan — works, but cross-platform support is brittle and performance on large subnets is poor.
- Pure Python discovery — rejected because Go's OS-level networking and concurrency are materially better for this job, and the whole point of the polyglot setup is to use the right tool per layer.

---

## 12. Authentication — JWT plus OAuth2, with Keycloak

**Decision:** SimpleJWT for the DRF API, django-oauth-toolkit for third-party clients, and Keycloak as the authorization server. DRF and the Go service are both resource servers.

**Why:**
- JWT is stateless. DRF validates the token locally against a published public key, with no session lookup. Scale from one uvicorn worker to ten without touching auth.
- The resource-server pattern centralizes credential handling. Keycloak is the only component that knows passwords. DRF and the Go service validate the same tokens with the same public key.
- Scopes live in the token. The trace endpoint requires `trace:execute`; the device list requires `device:read`. Revoke a user in Keycloak, their next refresh fails, and access disappears everywhere within the access-token lifetime.

**Alternatives rejected:**
- Django session auth — breaks under horizontal scaling. Sticky sessions, a shared session store, and cookie-domain headaches, all solved by stateless tokens.
- Symmetric signing (HS256) with a shared secret — the secret has to exist in every service that validates tokens. Asymmetric signing keeps the private key in one place.
- Rolling your own auth — the failure modes are subtle and the audit findings are expensive.

---

## 13. WebSockets via Django Channels

**Decision:** An ASGI worker, separate from the HTTP handler, owns the WebSocket connections. Nginx proxies the upgrade but does not own the state. Redis is the bridge between the Celery process and the ASGI process.

**Why:**
- Without WebSockets the browser polls every few seconds. With concurrent users that is redundant work on every poll. With a push, one Redis message reaches every connected browser in one operation.
- The ASGI worker and the HTTP handler have different lifecycles. The HTTP handler is stateless and scales freely. The ASGI worker holds long-lived connections, so it gets a fixed replica count, a PodDisruptionBudget, and a long termination grace period so rolling deploys do not drop everyone at once.

**Alternatives rejected:**
- Server-Sent Events — simpler, one-directional, but the dashboard also sends commands (trigger a trace), so bidirectional is the honest fit.
- Long polling — worse in every dimension than WebSockets for this workload.
- Holding WebSockets in Nginx — Nginx is a proxy, not an application server. Terminating application state there is a category error.

---

## 14. Observability — ddtrace, structlog, and SLOs

**Decision:** ddtrace auto-instrumentation plus manual spans, structlog for structured JSON logs, DogStatsD for custom metrics, and numeric SLOs for every critical path.

**Why:**
- Auto-instrumentation gives you traces across Django, Redis, Kafka, Celery, and Postgres with almost no code. Manual spans add the business context — subnet, task id, user id, devices found — that makes a trace searchable.
- Structured JSON logs are data, not strings. `{"event": "device_found", "mac": "...", "vendor": "..."}` is queryable. A formatted log line is something you grep and pray over.
- SLOs turn "the dashboard looks wrong" into a number with a threshold and an owner.

**The SLOs this system commits to:**
- Trace success rate above 99.5 percent over thirty days.
- Trace duration at the ninety-fifth percentile under forty-five seconds.
- Kafka consumer lag under one thousand messages.
- API latency at the ninety-fifth percentile under two hundred milliseconds.
- Redis cache hit rate above ninety percent.

**Alternatives rejected:**
- OpenTelemetry with Jaeger — a good stack, but Datadog gives the single-pane experience the learning goal asks for, and the local agent means no cloud account is needed to develop against it.
- The standard logging module with text output — rejected because unstructured logs are painful to query at the moment you need them most.

---

## 15. mTLS Between Services

**Decision:** Mutual TLS between the Celery worker and the Go service, and SASL over SSL between Python and Kafka. Certificates issued by an internal CA, managed by cert-manager.

**Why:**
- It stops an attacker who is already inside the perimeter. Without mTLS, anything that can reach the Go service port can inject a fabricated device with a MAC that matters to a compliance report.
- It is the direct answer to SOC2 (encryption in transit), ISO 27001 (authenticate the communicating parties), and PCI-DSS (both).
- Doing it manually here is how you understand what a service mesh automates. Istio and Linkerd give you this for free; knowing what they are doing is the difference between operating a mesh and being operated by one.

**Alternatives rejected:**
- Network policies alone — a good second layer, but they authenticate the network location, not the workload. A compromised pod inside the allowed range still gets through.
- API keys in headers — better than nothing, but a bearer token in transit without TLS is readable, and with TLS you have already done most of the work.
- No service-to-service auth because "it is an internal network" — this is the assumption every post-incident report starts with.

---

## 16. Kubernetes, Helm, and Nginx Ingress

**Decision:** k3s locally, Helm for packaging, one chart with three values files, Nginx ingress for TLS termination and WebSocket proxying.

**Why:**
- Helm's values-per-environment pattern is how real projects manage dev, staging, and production from one set of templates. Learning to structure a chart so the same template produces all three is a transferable skill.
- Nginx terminates TLS at the edge. The ASGI and DRF deployments speak plain HTTP internally, which means you can add and remove replicas without touching certificate configuration.
- Health checks split into liveness (restart if dead) and readiness (stop routing if it cannot serve). The preStop hook drains in-flight work before the container is killed.

**Alternatives rejected:**
- Docker Compose in production — fine for a single host, no story for scaling, rolling updates, or self-healing.
- Traefik instead of Nginx — k3s ships Traefik by default and it works, but Nginx is the more widely understood ingress and its WebSocket proxying is better documented.
- A service mesh from day one — justified at dozens of services, premature here. Phase 12's manual mTLS is the foundation that makes a mesh comprehensible later.

---

## 17. Terraform for Infrastructure

**Decision:** All cluster, networking, TLS, secrets, and monitoring configuration is Terraform code. Monitoring is defined as code, including the Datadog monitors.

**Why:**
- Terraform proves the infrastructure is reproducible. If the cluster dies, apply recreates it exactly — no guessing which security group changed last month.
- Monitoring as code means alerting rules are version-controlled and reviewed. A threshold change is a pull request with a reviewer, not a click in a web UI nobody can trace.
- Secrets live in Vault or a cloud secret manager, injected at runtime. Nothing sensitive is in Git, in Helm values, or in a container image.

**Alternatives rejected:**
- Click-ops in a cloud console — unreproducible, unauditable, and the first thing to break during an incident when nobody remembers what was changed.
- Helm for everything including the cluster — Helm deploys into a cluster; it does not create the cluster or the VPC. Terraform owns the substrate.
- Secrets in environment files baked into images — the classic leak. Rejected outright.

---

## 18. Operational Readiness — Health, Backups, Runbooks

**Decision:** Health checks at every layer, graceful shutdown everywhere, scheduled backups with a rehearsed restore, and a runbook attached to every alert.

**Why:**
- A health check that only pings the process is theater. The readiness check verifies the database, the cache, and the broker, so the load balancer stops routing to a pod that would only return errors.
- Graceful shutdown means SIGTERM drains in-flight requests and commits pending Kafka offsets before exit. Without it, every deploy drops work.
- A backup you have never restored from is not a backup. The restore is rehearsed on a schedule.
- A monitor without a runbook is noise. It pages someone who then has to figure out what to do from scratch, under pressure, at three in the morning. A monitor with a runbook pages someone who follows a documented procedure and resolves it in minutes.

---

## Explicit Non-Goals

- **IPv6.** IPv4 only, for clarity. The discovery layer would need parallel implementations.
- **Cross-subnet routing.** Scans are single-subnet. Routed ARP and multi-subnet sweep are a different project.
- **Deep mDNS inspection.** Hostname extraction is best-effort; full service-record enumeration is out of scope.
- **Load-testing to a million devices.** The schema and patterns support that scale, but the learning value is in the architecture, not in the benchmark.
- **A mobile app.** The dashboard is responsive; a native client is not part of the design.
