# Layout — Folder-by-Folder

This file explains why each path exists, what belongs in it, what does not, and how the structure maps to a production deployment. Use it as a reference while building; read DESIGN.md for the reasoning behind the choices.

---

## The Rule That Governs Everything

Dependencies point inward. The domain layer knows nothing about the layers above it. Infrastructure knows the domain. The web layer knows the application services. If you ever find the domain importing something from infrastructure, the design has been violated and the tests will eventually punish you for it.

```
Infrastructure-Web  ──knows──▶  Application  ──knows──▶  Domain
        │                              │
        └──────────knows──▶  Infrastructure
```

The web layer and infrastructure both sit at the edges. Neither knows about the other. The application layer orchestrates between them.

---

## Repository Root

```
device-manager/
```

**What lives here:** the docs, the build tooling, and the top-level configuration. Nothing else. If a file does not describe the project or configure the toolchain, it belongs in a subdirectory.

| Path | Purpose |
|---|---|
| README.md | Entry point. What the project is, the topology, the junior-to-senior framing |
| DESIGN.md | Every architectural decision and its rejected alternatives |
| LAYOUT.md | This file |
| PHASES.md | Build order from zero to production, with acceptance criteria |
| INFRA.md | Docker Compose, Kubernetes, Helm, Terraform structure |
| OPERATIONS.md | Health checks, shutdown, backups, runbooks |
| pyproject.toml | Python dependencies, tool configuration for uv and ruff, project metadata |
| uv.lock | Pinned dependency versions. Committed, so every environment is identical |
| Makefile | The command surface. Every recurring action has a target |
| .gitignore | Build artifacts, virtualenvs, certificates, secrets, caches |
| .env.example | Every environment variable with a safe default and a comment |

---

## proto/ — The Contracts

```
proto/
├── device_finding.avsc    Avro schema for a DeviceFinding
└── device.proto           gRPC service and message definitions
```

**What belongs here:** any schema that two different languages or two different services agree on. These files are the interface contracts, and a change to any of them is a commit with a message explaining why.

**Why it is at the root:** both the Go code and the Python code read from here. Putting it inside either language's tree would imply ownership by one side. The contract belongs to neither and both.

**The distinction that matters:** the Avro schema is the data contract for a finding. The proto is the RPC contract for calling the service. They evolve independently. You can add an RPC method without touching the Avro schema, and add an Avro field without regenerating stubs. Keeping them separate is deliberate.

---

## cmd/nettrace/ — Go Entrypoints

```
cmd/nettrace/
```

**What belongs here:** the main function and the command wiring. Thin. It parses flags, constructs the dependencies, and hands off to internal packages.

**Why the name:** the Go convention is `cmd/<binary-name>/`. The binary is called nettrace. Following the convention means any Go developer knows where the entrypoint is without being told.

---

## internal/ — Go Implementation

```
internal/
├── discovery/    ARP, mDNS, NetBIOS scanners and the merge logic
├── grpc/         gRPC server implementation
├── avro/         Avro encoder and decoder
└── model/        Pure Go types mirroring the schemas
```

**What belongs here:** everything the Go binary does that is not command wiring.

**Why `internal/`:** Go's compiler enforces that packages under `internal/` cannot be imported from outside the module. It is a language-level guarantee that the discovery implementation is private. This is the same instinct as the domain/infrastructure split in Python, enforced by the toolchain rather than by convention.

**The parallel to the Python layout:** `internal/model/` is the Go equivalent of the Python domain layer — pure types, no I/O. `internal/discovery/` and `internal/avro/` are infrastructure. `internal/grpc/` is the edge. The same layering discipline applies in both languages.

---

## src/device_manager/ — The Python Application

```
src/device_manager/
├── domain/
├── application/
├── infrastructure/
└── infrastructure_web/
```

**Why `src/`:** the package lives inside a `src/` directory rather than at the repository root. This is the modern Python packaging convention. It prevents accidental imports from the working directory — the tests import the installed package, not whatever happens to be sitting in the current folder. It also makes an editable install unambiguous.

---

### domain/ — Pure Business Logic

```
domain/
├── device.py      Device entity
├── finding.py     DeviceFinding value object
└── vendor.py      VendorLookup strategy interface
```

**What belongs here:** entities, value objects, domain events, and the interfaces (ABCs) that the outer layers implement. Business rules. State transitions. Nothing else.

**What must never appear here:** an import of SQLAlchemy, Django, Redis, Kafka, requests, or any I/O library. If the domain layer needs to talk to the outside world, it declares an interface and lets infrastructure implement it.

**Why it matters:** this is the layer you never rewrite. Change the database, the cache, the message broker, the web framework — the domain code does not move, and the domain tests do not change. That is the entire return on the architectural discipline, and it evaporates the moment a framework import leaks in.

**The entity versus value-object distinction:** a Device is mutable — its IP changes, its last-seen timestamp advances, its status transitions. A DeviceFinding is immutable — it is a record of one observation at one instant, and mutating it would be a lie. One is a frozen dataclass, the other is not. That is not stylistic; it is the difference between current state and historical fact.

---

### application/ — Orchestration

```
application/
├── services/
│   ├── device_service.py        Ingest a finding, update state
│   ├── trace_coordinator.py     Invoke the Go service, handle results
│   └── cache_service.py         Read-through cache behavior
└── consumers/
    ├── kafka_ingestion_consumer.py   Findings to domain to database
    ├── websocket_consumer.py         Push updates to browsers
    └── metrics_consumer.py           Emit observability metrics
```

**What belongs here:** use cases. The application layer orchestrates — it calls the domain, calls the repositories, calls the external services, and enforces the order of operations. It contains workflow, not business rules.

**The distinction from the domain:** the domain decides whether a device is new. The application layer decides what happens when a device is new — invalidate the cache, publish an event, emit a metric, notify the dashboard. Rules live in the domain; coordination lives here.

**The distinction from infrastructure:** the application layer defines what it needs (a repository, a producer, a cache) through interfaces. Infrastructure provides the implementations. The application layer never imports a concrete adapter.

---

### infrastructure/ — Adapters and Side Effects

```
infrastructure/
├── persistence/
│   ├── sqlalchemy_models.py     ORM models
│   ├── session.py               Engine and session factory
│   └── migrations/              Alembic environment and revisions
├── repositories/
│   ├── device_repository.py     The interface, mirrored from the domain
│   ├── sqlalchemy_device_repo.py
│   ├── in_memory_device_repo.py
│   └── caching_device_repo.py
├── redis_client.py
├── kafka_producer.py
└── grpc_client.py
```

**What belongs here:** everything that touches the outside world. Database engines, ORM models, migrations, cache clients, message producers, RPC clients, third-party SDKs. All the side effects live here.

**The repository decorator pattern:** `caching_device_repo` wraps any other repository. It checks Redis first, falls through to the wrapped repository on a miss, and invalidates on write. Because it implements the same interface, you can compose it — Postgres wrapped in cache, or in-memory wrapped in cache for tests — without the application layer knowing the difference.

**Why migrations live in infrastructure:** the schema is an implementation detail of the persistence choice. The domain does not know what a table is. Alembic revisions belong next to the ORM models they correspond to.

---

### infrastructure_web/ — The HTTP and WS Edge

```
infrastructure_web/
├── main.py             ASGI application assembly
├── settings.py         Django and Channels configuration
├── urls.py             URL routing
├── serializers.py      Request and response shapes
├── permissions.py      Scope checks
└── routers/
    ├── devices.py
    ├── events.py
    └── trace.py
```

**What belongs here:** the translation layer between HTTP/WebSocket and the application services. Serializers, viewsets, permissions, URL routing, ASGI assembly.

**What must never appear here:** business logic. If a router is deciding whether a device counts as new, that decision has leaked out of the domain. The router's job is to validate input, check permissions, call a service, and shape the response.

**Why it is a separate package from infrastructure:** both sit at the edge, but they are different edges. Infrastructure talks to databases and brokers. The web layer talks to browsers and API clients. Keeping them apart means the web layer can be replaced — swap DRF for FastAPI, add a GraphQL gateway — without touching a single adapter.

**The 202 pattern lives here:** the trace router validates the subnet, checks the scope, enqueues the task, and returns accepted with a task id. It does not run the scan. That separation is what keeps the HTTP worker free.

---

## frontend/ — The Dashboard

```
frontend/
├── src/
│   ├── App.jsx
│   ├── api.js                 Fetch wrapper with auth and refresh
│   ├── useWebSocket.js         Connection hook with backoff
│   └── components/
│       ├── DeviceTable.jsx
│       ├── VendorPie.jsx
│       ├── TimelineChart.jsx
│       ├── NewDeviceAlert.jsx
│       └── TraceButton.jsx
├── nginx.conf
└── package.json
```

**What belongs here:** the browser application and the Nginx configuration that serves it.

**Why nginx.conf lives with the frontend:** the Nginx config is frontend concerns — TLS, static file serving, SPA routing fallback, and the WebSocket upgrade headers. It is not a backend concern. Keeping it here means the frontend can be built, served, and reasoned about as one unit.

---

## tests/ — Mirrored Structure

```
tests/
├── conftest.py                 Shared fixtures: fake repo, fake vendor lookup
├── domain/                     No infrastructure imports allowed
├── application/                Fakes only, no real database
└── infrastructure/             May use real services via Docker
```

**What belongs here:** tests, organized to mirror the source tree.

**The rule enforced by structure:** tests under `domain/` and `application/` run with zero infrastructure. They use the in-memory repository and the in-memory vendor lookup. Tests under `infrastructure/` are allowed to talk to Docker. The folder boundary is the contract — if an application test needs Postgres, the seam in the design is in the wrong place.

---

## infra/ — Deployment

```
infra/
├── docker-compose.yml          Local dev: Postgres, Redis, Kafka, Keycloak, Datadog
├── k8s/                        Raw manifests for reference
├── helm/
│   └── device-manager/
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── values-dev.yaml
│       ├── values-staging.yaml
│       ├── values-prod.yaml
│       └── templates/
└── terraform/
    └── modules/
```

**What belongs here:** everything needed to run the system somewhere other than a laptop.

**The progression:** Docker Compose for local development. Raw Kubernetes manifests as a learning reference. Helm as the real packaging, with one chart and three values files. Terraform as the substrate — it creates the cluster, the network, the DNS, and the certificates that Helm then deploys into.

**See INFRA.md** for the full structure of the Helm templates and Terraform modules.

---

## scripts/ — Operational Helpers

```
scripts/
└── dev.sh
```

**What belongs here:** one-off operational scripts — seeding vendor data, running a local trace, resetting the development database. Things a human runs, not things the application runs.

---

## Import Rules, Summarized

| Layer | May import | Must never import |
|---|---|---|
| domain | itself, standard library | application, infrastructure, infrastructure_web, any framework |
| application | domain, its own interfaces | infrastructure implementations, infrastructure_web |
| infrastructure | domain, application interfaces | infrastructure_web |
| infrastructure_web | application, domain types | infrastructure implementations directly (use interfaces) |

The enforcement is convention plus review, not a compiler. That is the honest answer. Tools exist that can check import boundaries, and adding one is a reasonable hardening step, but the discipline starts with knowing the rule.

---

## How the Structure Maps to Production

| Source folder | Deploys as | Scaling behavior |
|---|---|---|
| infrastructure_web (HTTP) | DRF deployment, multiple replicas | Stateless, scales horizontally on CPU |
| infrastructure_web (ASGI) | Separate deployment holding WebSocket connections | Fixed replicas, PodDisruptionBudget, long grace period |
| application/consumers | Celery worker deployment | Scales on queue depth |
| application (Faust) | Stream processor deployment | Fixed replicas, one per partition group |
| cmd/nettrace + internal | Go service deployment | One replica per node; it scans the local network |
| infrastructure/persistence | Postgres StatefulSet with PVC | Vertical, then read replicas |
| infrastructure (Redis) | Redis deployment | Sentinel or Cluster for high availability |
| frontend | Nginx serving a static build | Stateless, scales freely |

The folder structure is not arbitrary aesthetics. Each directory corresponds to a deployment unit with its own lifecycle, its own scaling rule, and its own failure mode. When you understand the layout, you understand the topology.
