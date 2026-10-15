# Phases — Build Order

Work through these in order. Each phase produces something runnable you can observe, and each builds on the previous. By the final phase you have a production-grade deployment managed by Terraform and Helm with full observability.

A phase is complete when its acceptance criteria pass — not when you feel like moving on. The criteria are deliberately concrete so there is no ambiguity about done.

**How to use this file:** read one phase, build what it describes, confirm the acceptance criteria, then move to the next. Do not read all phases up front. You will design the wrong abstractions if you try to plan for phase twelve while building phase one. Build phase one, feel the seams, then read phase two.

---

## Phase 0 — Project Skeleton

**Goal:** establish the toolchain and the folder structure so every later phase has somewhere to put things.

**What you build:** an empty but correctly structured project. The uv and ruff configuration. The folder scaffold with placeholder package markers. The gitignore and environment example. A Makefile with the recurring commands as targets.

**What you learn:** how uv creates the virtual environment and installs from the project file; how ruff lints and formats; why the package lives inside a `src/` directory rather than at the repository root; and that folder structure is a contract between you and your future self.

**Why it matters in production:** a reproducible development environment is the first defense against "works on my machine." A committed lockfile pins exact versions. A linter enforces one style across every contributor. These are not polish — they are the difference between onboarding a new engineer in an hour versus a week.

**Acceptance criteria:** dependency sync succeeds; the linter passes on an empty tree; the formatter makes no changes; the folder tree matches the layout document.

---

## Phase 1 — Domain Layer with Fakes and Tests

**Goal:** write the business logic and test it with no infrastructure running at all. No database, no cache, no broker. Pure Python.

**What you build:** the Device entity, the DeviceFinding value object, and the VendorLookup strategy interface with an in-memory implementation. A repository interface with an in-memory fake. A device service that accepts both through its constructor. Tests for MAC normalization, observation, status transitions, serialization round-trips, vendor lookup, and the ingest flow.

**What you learn:** abstract base classes for interfaces; frozen dataclasses for value objects; enums for bounded state; constructor injection as the mechanism for swapping implementations; and writing tests against interfaces so the fake and the real thing are interchangeable.

**Why it matters in production:** this is the layer you never rewrite. When the database changes, the domain code does not move and the domain tests do not change. That is the entire return on the architectural discipline, and it only materializes if you enforce the boundary from the first commit.

**Acceptance criteria:** all domain and application tests pass; coverage of the domain layer above ninety percent; no test imports anything from the persistence or cache modules; three different MAC input formats all normalize to the same canonical form.

---

## Phase 2 — SQLAlchemy, Alembic, and Postgres

**Goal:** wire the real database. The SQLAlchemy repository replaces the in-memory fake. Alembic owns the schema. The application service does not change — it still accepts a repository interface, just a different implementation.

**What you build:** ORM models for devices, events, and vendors. An async engine and session factory initialized once at startup. The real repository, translating between ORM rows and domain objects. An Alembic environment configured for async, plus a first revision creating the tables and indexes. A Docker Compose service for Postgres with a health check and a wait loop.

**What you learn:** SQLAlchemy's async engine and session patterns; modern declarative model definitions; Alembic's async bridge; Docker Compose health checks; and the unit-of-work pattern at the session level — one session per operation, commit on success, rollback on failure.

**Why it matters in production:** this is the persistence layer that survives every rewrite above it. When you need to add a column, you add it to the model and write a migration. The domain never knows. Alembic is the migration tool production Postgres projects actually use; learning it here means you are not learning it under pressure during a schema change at two in the morning.

**Acceptance criteria:** Postgres comes up healthy; the migration creates the tables and records the revision; all phase-one tests still pass unchanged; a parameterized test runs the same ingest against both the fake and the real repository and produces identical domain output; querying the table directly shows the upserted row.

---

## Phase 3 — Apache Avro as the Wire Format

**Goal:** define the schema, encode in Go, decode in Python, and prove the two languages agree by round-tripping a message by hand with no services running.

**What you build:** the Avro schema file for a DeviceFinding, using nullable unions for optional fields and a microsecond logical timestamp. A Go encoder that takes the Go struct and produces bytes. A Python decoder using fastavro. Round-trip tests in both languages that prove the same bytes decode to the same fields regardless of which side encoded them.

**What you learn:** schema design with unions and defaults; why microsecond timestamps beat both milliseconds and ISO strings at this volume; and the schema evolution rule — adding a nullable field with a default is forward compatible, removing one is backward compatible, and changing a type breaks everything.

**Why it matters in production:** the schema is a contract between services in different languages, possibly owned by different teams, deployed on independent schedules. Right now the contract is a file both sides agree on. In the Kafka phase it becomes a registry that enforces the contract at runtime — a producer cannot send what the registry rejects, and a consumer cannot read a version it did not opt into. That is the difference between a pipeline that works today and a pipeline that still works after someone changed the schema last Tuesday.

**Acceptance criteria:** the Go encoder test passes; the Python round-trip test passes; the same byte sequence decodes to identical findings regardless of which language encoded it.

---

## Phase 4 — The Go Service

**Goal:** build the binary that scans a subnet and serves findings over gRPC, in two modes: a one-shot CLI for development and a long-running server for production.

**What you build:** a command-line entrypoint with a trace subcommand and a serve subcommand. The trace mode runs the scanners and prints results. The serve mode starts a gRPC server with a unary call for a one-shot scan and a streaming call that pushes findings as they are discovered. Three discovery mechanisms — reading the kernel ARP cache, sending mDNS multicast queries, and firing NetBIOS name requests — running in parallel and merged by MAC address. A context-derived timeout so a hung scan is cancelled rather than lingering.

**What you learn:** command-line framework structure; Go module organization; gRPC service registration, streaming responses, and deadline propagation; goroutines and wait groups for parallel I/O; parsing the kernel ARP table without elevated privileges; mDNS multicast and NetBIOS name resolution; and encoding against an Avro schema in Go.

**Why it matters in production:** this is the part of the system that touches the network, so it has to be fast, correct, and reliable. Writing it in Go gives you goroutines for parallel I/O without interpreter lock contention, and a static binary that deploys anywhere. The long-running server mode is what production uses — it is a separate deployable artifact, supervised by the platform, and if it crashes the backend is unaffected.

**Acceptance criteria:** the binary compiles; the CLI trace prints results for a subnet; the Avro output round-trips; the server starts and passes a gRPC health check; a gRPC client call returns a task identifier and a device count; a scan that exceeds its deadline returns a deadline-exceeded error rather than hanging.

---

## Phase 5 — DRF, the HTTP API

**Goal:** build the API the browser talks to. ViewSets, serializers, permissions, pagination, CORS. The trace endpoint is the centerpiece — it enqueues work and returns accepted immediately.

**What you build:** the ASGI application assembly and Django settings. Serializers for devices, events, vendors, and the trace request, with subnet validation. Pagination configured differently for the current-state endpoints (offset) and the append-only event log (cursor). Three routers: devices, events, and trace. The trace router enqueues a task and returns a task id; a retrieve action reports task status; a list action shows the caller's own trace history. Permission classes that require authentication and check the token's scope before any business logic runs.

**What you learn:** ViewSet and router structure; how permission classes run before your code, making them the enforcement point; serializer validation and read-only fields; the difference between cursor and offset pagination and when each is correct; CORS and browser preflight; and the accept-and-poll pattern that decouples the HTTP request from long-running work.

**Why it matters in production:** this layer is the boundary between the internet and your system. Every security rule lives here — authentication, authorization, input validation, rate limiting, CORS. It is the layer that gets audit-reviewed. Treating it as "just routing to the service" is how enforcement points get missed, and attackers find missed enforcement points.

The accept-and-poll pattern is standard for a reason. The browser does not hang for sixty seconds. The web worker is not blocked. The queue owns the retry, timeout, and visibility story. This is the same approach every major cloud provider uses for asynchronous APIs.

**Acceptance criteria:** token issuance works; the device list returns successfully with a valid token; a trace request returns accepted with a task id; the task status endpoint reports the current state; an invalid subnet returns a validation error; a missing token returns unauthorized; a token without the required scope returns forbidden; the CORS preflight returns the correct headers for the frontend origin.

---

## Phase 6 — Redis, Three Roles

**Goal:** use Redis as the cache, as the Celery broker, and as the pub/sub bridge between the Celery process and the ASGI process — and understand that these are three different reliability profiles, not one thing called Redis.

**What you build:** a client wrapper providing cache get and set with TTL, cache invalidation, and publish and subscribe. A repository decorator that wraps any repository with a read-through cache, falling through on a miss and invalidating on every write. The Channels Redis layer configuration that connects the publishing process to the WebSocket-holding process. A Docker Compose service for Redis.

**What you learn:** the cache-aside pattern with write-through invalidation; how a broker queue differs from a pub/sub channel (one is durable until consumed, the other is ephemeral); why the Celery broker needs persistence but the cache and the event channel do not; and how the Channels layer uses Redis pub/sub under the hood to bridge two separate processes.

**Why it matters in production:** Redis is the connective tissue of this system. Cache, broker, and event bus — three reliability profiles on one process. A senior engineer knows which persistence setting protects which role: the cache may lose data and regenerate, the broker queue must survive restarts or work is lost, the event channel may drop messages because the next scan refreshes the dashboard. A junior enables snapshots, calls it done, and is surprised when a restart loses queued tasks.

**Acceptance criteria:** Redis comes up healthy; the caching repository tests pass, covering miss-then-populate, invalidation on update, and TTL expiry; a publish and subscribe round-trip test passes; the Celery worker connects to the broker successfully; and the trace endpoint responds in under a hundred milliseconds because it only enqueues.

---

## Phase 7 — Kafka, the Durable Event Log

**Goal:** add Kafka as the transport and history. The Celery worker publishes each finding. Three consumers read the same topic independently — ingestion, aggregation, and metrics — with no coupling between them.

**What you build:** a producer wrapper configured for batching and compression. An ingestion consumer in its own consumer group that deserializes each finding, calls the same ingest service the HTTP path uses, publishes a WebSocket event on success, and commits its offset only after the database write succeeds. A Faust stream processor maintaining a tumbling window of new devices per minute, materialized into Postgres. A metrics consumer in its own group that counts by vendor and emits gauges. A Kafka service in KRaft mode with the three topics pre-created.

**What you learn:** topic, partition, and consumer group semantics; producer configuration for latency versus throughput; how consumer group rebalancing distributes partitions; the exactly-once ideas — idempotent writes plus offset commits after the database write; Faust applications, agents, streams, tables, and tumbling windows; and how to inspect a topic with command-line tooling.

**Why it matters in production:** this is the decision that separates a toy from a real event-driven system. The scanner produces findings; it does not know how many consumers exist. Adding a fourth consumer — alert on unknown MACs, feed a configuration database, export to a security platform — requires no producer change. Kafka is durable: a consumer that was down for twenty minutes catches up from its committed offset, and one that crashed mid-write gets the message redelivered, where the idempotency key absorbs the duplicate. Postgres is the source of truth; Kafka is the transport and the history. They serve different purposes and the design keeps them distinct.

**Acceptance criteria:** Kafka comes up healthy with all three topics present; triggering a trace causes all three consumers to process the findings independently — devices appear in Postgres, the stats table gains windowed rows, and the metrics increment; adding a second ingestion consumer splits the partitions between them without producing duplicates; replaying from the beginning of the topic still yields the first message; and retention expiry removes old messages on schedule.

---

## Phase 8 — JWT and OAuth2 Authentication

**Goal:** replace development-placeholder auth with real token-based authentication. Keycloak as the authorization server, DRF and the Go service as resource servers, scopes enforced per endpoint.

**What you build:** authentication configuration using asymmetric signing so only the authorization server holds the private key. A token issuance serializer that adds the scope claim derived from group membership. A custom permission class that checks the required scope on each endpoint. A Keycloak service with a seeded realm, a bearer-only client, two groups, and protocol mappers that translate group membership into the scope claim.

**What you learn:** token structure and encoding; why asymmetric signing beats a shared secret when multiple services validate tokens; how a resource server fetches public keys instead of holding secrets; the resource-server pattern where the API never handles passwords; scope-based authorization checked at the permission layer; and the token refresh flow with short access tokens and longer refresh tokens.

**Why it matters in production:** session-based authentication breaks the moment you scale horizontally — sticky sessions, a shared session store, cookie domain problems. Stateless tokens eliminate all of it. The resource-server pattern centralizes credential handling in one place; both the Python and Go services validate the same tokens with the same public key. Revoking a user removes their access everywhere within the access-token lifetime. This is the enterprise authentication standard, and this phase is how you learn it by building it.

**Acceptance criteria:** the authorization server is up with the realm configured; token issuance returns a token carrying a scope claim; an endpoint requiring a scope the token lacks returns forbidden; the same endpoint with the correct scope succeeds; a tampered token fails signature validation; an expired token is rejected; refreshing with a valid refresh token issues a new access token; and the public key endpoint returns the key set.

---

## Phase 9 — WebSockets for the Live Dashboard

**Goal:** replace polling with push. The browser opens a WebSocket, the Celery worker publishes to Redis, the ASGI worker pushes to the browser. No reload, no polling, no wasted requests.

**What you build:** an ASGI application that routes both HTTP and WebSocket protocols. An authentication middleware that validates the token during the WebSocket handshake. A consumer that accepts authenticated connections, joins them to a group, and sends JSON on group messages. The channel layer configuration backed by Redis, which bridges the publishing process and the connection-holding process. A publish call in the ingestion consumer, fired after the database write commits. A frontend hook that connects, handles messages, and reconnects with exponential backoff.

**What you learn:** the difference between ASGI and WSGI and why WebSockets require the former; protocol routing in one application; consumer lifecycle methods; handshake authentication via query parameter because browsers cannot set headers on a WebSocket upgrade; group messaging as the fan-out primitive; bridging synchronous and asynchronous code; the WebSocket lifecycle including close codes and reconnection; and why the connection-holding process is a separate deployment from the stateless HTTP handler.

**Why it matters in production:** this is what makes the dashboard feel alive. Without it the browser polls every few seconds, and with concurrent users that is redundant work on every poll. With a push, one Redis message reaches every connected browser in a single operation — the server does the work once instead of fifty times.

The separate-deployment decision follows from the lifecycle difference. The HTTP handler is stateless and scales freely. The connection holder is stateful; restarting it drops every connected browser. That is why it gets a fixed replica count, a disruption budget that prevents all replicas from being evicted at once, and a long termination grace period that drains connections before shutdown.

**Acceptance criteria:** an authenticated handshake is accepted and stays open; an unauthenticated handshake is rejected; a trace while a client is connected delivers a message within two seconds; two connected tabs both receive the same push; restarting the connection holder causes clients to reconnect within thirty seconds; and a message published directly to the channel reaches connected clients within half a second.

---

## Phase 10 — Observability

**Goal:** instrument the whole system. Distributed traces crossing DRF, Celery, Kafka, and Postgres. Structured JSON logs. Custom metrics with numeric targets. This is the phase that turns "it works" into "I know why it works and I will know when it stops."

**What you build:** auto-instrumentation enabled at startup so the framework, the cache client, the broker, and the database driver all emit spans without code changes. Manual spans around the business operations, tagged with subnet, task id, user id, and device count. Structured logging configured to emit JSON with request-scoped context merged in. Custom metrics for trace starts, durations, consumer lag, cache hit rate, and device counts. Numeric targets for success rate, latency, lag, and cache effectiveness. A local observability agent so the whole workflow is developable without a cloud account.

**What you learn:** what auto-instrumentation covers and where manual spans add the context that makes a trace searchable; how a trace ID propagates across process boundaries through message headers so one flame graph spans Go, Kafka, Celery, and Postgres; structured logging as queryable data rather than grep targets; the metric types and when each applies; and defining health as a number with a threshold and an owner rather than as an opinion.

**Why it matters in production:** observability separates senior from junior more than any other single skill. When the dashboard shows zero devices and the scan found forty, the junior greps logs, adds print statements, restarts the worker, and eventually finds it by luck. The senior opens the trace, sees the produce step took two hundred milliseconds instead of five, drills into that span, sees it is waiting on replication acknowledgement, checks the cluster, finds a broker down, and pages the infrastructure team with the broker name and the affected partition count — without reading a single log line. That is the payoff for doing this phase properly.

The structured logging format matters for the same reason. A formatted log line is a string you grep. A JSON log line is data you query by field. The second is how production systems are actually debugged.

**Acceptance criteria:** the agent receives traces; a triggered trace appears in the trace viewer with spans for the HTTP request, the task, the produce, and the database queries, all sharing one trace identifier; log output is JSON rather than formatted text; filtering logs by event type returns the matching lines with no regular expressions; custom metrics are visible and incrementing; and every span carries the business tags needed to find one specific trace.

---

## Phase 11 — The React Frontend

**Goal:** build the dashboard the WebSocket pushes to. A device table, a vendor chart, a discovery timeline, and a new-device alert. Served through Nginx with TLS.

**What you build:** a sortable, filterable device table that highlights recently seen devices and virtualizes once the row count grows large. A vendor distribution chart that filters the table when a slice is clicked. A timeline chart reading from the materialized aggregation and updating on push. A toast notification for new devices with a stack limit and auto-dismiss. A trace button that validates the subnet, submits, and shows progress. An API client that attaches the token, refreshes on expiry, and retries the original request. A WebSocket hook with exponential backoff on reconnection. An Nginx configuration serving the built assets, handling single-page routing, proxying the API, and proxying the WebSocket upgrade.

**What you learn:** function components and hooks; chart library integration; the WebSocket lifecycle in the browser including reconnection strategy; single-page routing with a server fallback; the build tool's development server and environment variables; the specific Nginx headers required to proxy a WebSocket upgrade; table virtualization for large datasets; optimistic updates driven by pushes; and the trade-offs of storing tokens in browser storage.

**Why it matters in production:** the frontend is where every architectural decision becomes visible to the user. The accept-and-poll pattern means the trace button does not hang. The WebSocket means no reload. The cache means the table loads fast even when the database is slow. The observability means you know the reconnection rate before users complain. And the Nginx WebSocket proxy configuration is a specific, non-obvious piece of knowledge — the upgrade headers are required, not optional, and TLS terminates at the proxy rather than in the application so replicas can come and go without certificate reconfiguration.

**Acceptance criteria:** the production build succeeds; the development server renders the dashboard; triggering a trace populates the table; a pushed update raises the toast, highlights the row, and advances the timeline; sorting and filtering behave correctly; disconnecting the connection holder shows a disconnected status and the client reconnects after the server returns; and the dashboard is served over TLS through the proxy.

---

## Phase 12 — mTLS Between Services

**Goal:** add mutual TLS between the Celery worker and the Go service, and authenticated encryption between Python and Kafka. Without this, any process that can reach the port can inject fabricated findings.

**What you build:** an internal certificate authority and the server and client certificates it issues, with subject alternative names matching the in-cluster service DNS names. The Go server configured to require and verify a client certificate. The Python client configured to present its certificate on every call. Kafka configured to require authentication over TLS. Certificate resources so the cluster issues and renews these automatically.

**What you learn:** how TLS authenticates the server to the client and how mutual TLS adds client authentication in the other direction; certificate chains from root through intermediate to leaf; why subject alternative names replaced common-name matching and how cluster DNS maps to them; the server and client configuration in both languages; the ladder of Kafka security protocols from plaintext through TLS to authenticated TLS; and why a service mesh automates exactly this — building it manually is how you understand what the mesh does for you.

**Why it matters in production:** this stops an attacker who has already breached the perimeter. Once inside the network, without mutual authentication anyone can call the scan service and tell it to find a device that does not exist, with a MAC address that matters to a compliance report. With mutual TLS that call fails because there is no CA-signed client certificate. This is the direct answer to the encryption-in-transit and authenticate-the-parties requirements that appear in every compliance framework. In a mesh it is automatic; outside a mesh, doing it by hand is the foundation that makes a mesh comprehensible.

**Acceptance criteria:** the authority and certificates are generated; the Go service starts requiring mutual TLS; a client with a valid certificate succeeds; a client without a certificate is rejected; a certificate signed by a different authority is rejected; Kafka rejects plaintext connections and rejects authenticated connections with wrong credentials; and a packet capture shows the mutual handshake and encrypted application data.

---

## Phase 13 — Kubernetes, Helm, and Ingress

**Goal:** deploy to a cluster with Helm. One chart, three environment configurations. Ingress for TLS termination and WebSocket proxying. Health checks, resource limits, and graceful shutdown. This is where the project becomes a system.

**What you build:** a Helm chart with shared defaults and per-environment overrides. Templates for each deployment: the HTTP handler, the WebSocket holder, the Celery worker, the Go service, the stream processor, the frontend, and the stateful database. Services for each. An ingress terminating TLS and proxying both the API and the WebSocket upgrade. Liveness and readiness probes on every deployment, with a pre-shutdown hook that drains in-flight work. A horizontal autoscaler for the stateless HTTP handler. A disruption budget for the WebSocket holder so rolling updates never evict every connection at once. Network policies restricting which pods can reach which ports. Certificate resources for automatic issuance and renewal.

**What you learn:** Helm chart structure, templating, values overrides, and using published charts as dependencies; the Kubernetes resource types and when each applies; the difference between liveness and readiness and why both exist; graceful shutdown through hooks, signal handling, and grace periods; certificate management automation; ingress configuration for TLS, WebSocket proxying, and rate limiting; and the specifics of running a lightweight single-node cluster locally.

**Why it matters in production:** this is where the architecture becomes something you could actually run. The decision to use a queue for the trace means the HTTP handler scales horizontally. The decision to hold WebSockets in a separate process means that deployment gets a disruption budget and a long grace period. The decision to use mutual TLS means the network policy is a second layer of defense rather than the only one. And the one-chart-many-values-files pattern is how every real project manages per-environment configuration — learning to structure it so the same template produces a development cluster and a production cluster is a skill that transfers to every deployment you will ever touch.

**Acceptance criteria:** installing with the development values brings every pod to running and ready; the readiness endpoint reports the health of the database, cache, and broker; the dashboard loads over TLS through the ingress and the WebSocket connects through it; a full trace works end to end in the cluster; deleting an HTTP pod causes zero downtime; deleting the database pod restarts it with data intact and the readiness endpoint degrades until it returns; and scaling the HTTP deployment keeps the dashboard responsive.

---

## Phase 14 — Terraform and Production Operations

**Goal:** provision the cluster and its supporting infrastructure as code. Add the operational layer: secrets management, scheduled backups with a rehearsed restore, alerting defined as code with runbooks, and the observability dashboards. This is where the project becomes something you could hand to an operations team.

**What you build:** Terraform modules for the cluster, the networking, the certificate issuers, the secrets store, and the monitoring. The secrets module holds the database password, the token signing key, and the broker credentials in a secret manager, injected at runtime so nothing sensitive is in version control or in a container image. The monitoring module defines the alerting rules as code, each with a message linking to its runbook. A scheduled backup job dumping the database to deduplicating object storage with a retention policy. An operations document covering where to look first when an alert fires, the response to each common alert, the deploy and rollback procedures, the scaling decision for each component, and the incident response and post-mortem template.

**What you learn:** infrastructure-as-code structure including modules, state, and the plan-apply cycle; using Terraform to drive both the cluster and the Helm releases into it; defining monitoring as code so alert changes are reviewed like any other change; secret management with a dedicated store and runtime injection; backup strategy including logical dumps, deduplicating storage, and retention; the three-copy two-media one-offsite rule; and the principle that every alert must have a documented response.

**Why it matters in production:** Terraform proves the infrastructure is reproducible — if the cluster dies, apply recreates it exactly, with no guessing which setting drifted. Monitoring as code means alerting rules are version-controlled and reviewed rather than clicked into a console nobody can audit. And the runbook is the single most important artifact in this phase. A monitor without a runbook is noise: it pages someone who must figure out what to do from scratch, under pressure, in the middle of the night. A monitor with a runbook pages someone who follows a documented procedure and resolves it in minutes. The runbook is the difference between an alert that helps and an alert that trains people to ignore alerts.

**Acceptance criteria:** the infrastructure plan shows the resources to be created with no errors; applying provisions the cluster, DNS, certificates, secrets, and monitors; the production deployment runs on the provisioned cluster; the dashboard is live over TLS with a valid certificate; a full trace works end to end in production; deliberately stalling a consumer fires the lag alert within ten minutes and the alert links to its runbook; the backup job has run, the snapshot is listed, and a restore to a scratch database matches the row counts; tearing down the infrastructure cleans up everything, proving it is reproducible; and the operations document covers deploy, rollback, scaling, backup and restore, and at least five alert runbooks.

---

## What You Have Built

A system that discovers devices with a Go service scanning three protocols in parallel; transports findings through a durable, replayable event log with multiple independent consumers; stores state in PostgreSQL with versioned migrations; caches hot reads in Redis with write-through invalidation; serves a REST API with scoped token authentication; pushes live updates to browsers through a proxied WebSocket; traces every request across service boundaries; degrades gracefully when any single dependency fails; deploys reproducibly from one chart across three environments on infrastructure defined entirely as code; and alerts with documented runbooks so a three-in-the-morning page is a procedure rather than a puzzle.

And you understand, because you built each piece, why it is there. That is the difference between a project and a production system.
