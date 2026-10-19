# Expense Tracker — Learning Project

An enterprise-grade expense tracker built as a **learning vehicle** for a modern
Python backend + cloud-native deployment stack. The React UI is out of scope for
learning (auto-generated via LLM), but its placement in the system is documented so
the backend can be designed against it correctly.

> **Golden rule for this repo:** Claude writes **documentation only**. You write
> the application code, phase by phase, using these docs as your guide. If you want
> code, you ask for it explicitly.

---

## What you are actually here to learn

The expense tracker is the vehicle. These are the skills — each has a dedicated guide:

| Skill | Guide | You'll be able to… |
|-------|-------|--------------------|
| **Architecture, patterns & system design** | [`architecture-patterns.md`](docs/architecture-patterns.md), [`design-patterns.md`](docs/design-patterns.md), [`system-design.md`](docs/system-design.md) | Choose boundaries and patterns deliberately; reason about scale, reliability, consistency, and trade-offs |
| **Object-oriented principles** | [`oop-principles.md`](docs/oop-principles.md) | Apply SOLID, composition, encapsulation, and YAGNI without over-engineering |
| **Break a problem into entities & classes** | [`domain-decomposition.md`](docs/domain-decomposition.md) | Turn a fuzzy idea into models, boundaries, and relationships you can defend |
| **DRF + JWT + OAuth hands-on** | [`drf-jwt-guide.md`](docs/drf-jwt-guide.md) | Build, secure, and reason about authenticated REST endpoints |
| **Postgres: basics → tuning → observability** | [`postgres-guide.md`](docs/postgres-guide.md) | Model, index, tune, and watch a real database |
| **Records, events, cleanup, archival** | [`data-lifecycle.md`](docs/data-lifecycle.md) | Decide what lives hot, what goes cold, and when to delete |
| **Kafka topics, retention, schemas** | [`kafka-guide.md`](docs/kafka-guide.md) + [`avro-guide.md`](docs/avro-guide.md) | Design topics, evolve schemas, and reason about delivery guarantees |
| **Infrastructure: Terraform, k3s, Helm, edge** | [`infrastructure.md`](docs/infrastructure.md) | Provision and deploy the whole thing reproducibly |
| **NGINX: process model → ingress → limits** | [`nginx/`](docs/nginx/) | Understand the edge; tune and debug it |
| **TLS: handshake → certs → topology** | [`tls/`](docs/tls/) | Trust the network, and prove the certificate is right |
| **Rate limiting: algorithms & where they live** | [`rate-limiting.md`](docs/rate-limiting.md) | Choose a limiter per situation, not one everywhere |

Everything else (project layout, API contracts, phases, checkpoints) exists to
support these. When a guide feels abstract, the phases tell you when to actually
build it.

---

## What you are learning (the stack)

| Area | Technology | Why it is in this project |
|------|-----------|---------------------------|
| Python project tooling | `uv`, `ruff` | Fast, reproducible Python envs and linting |
| Web framework | Django + Django REST Framework (DRF) | Enterprise REST APIs, ORM, admin, migrations |
| API contracts | OpenAPI 3.1 / Swagger | Every endpoint documented and typed |
| Database | PostgreSQL | Primary relational store |
| Connection pooling | PgBouncer | Handle many short-lived connections |
| ORM / migrations | SQLAlchemy (2.0 style) or Django ORM | Enterprise data access layer |
| Auth | JWT + OAuth2 (social login) | Stateless API auth |
| Event streaming | Apache Kafka + Avro (`.avsc`) | Async expense → loan updates |
| Containers | Docker / k3s | Lightweight Kubernetes at the edge |
| Deploy infra | Terraform | Reproducible cluster + cloud provisioning |
| Packaging | Helm | Versioned, parameterized k8s deploys |
| Observability | Datadog / Grafana / Kafka charts | Kafka streams, ingress, latency, egress |
| Edge | NGINX (Ingress + load balancing + rate limiting) | Traffic management |
| Data lifecycle | PVC archival of historical events | Cheap long-term event retention |
| Networking | Tailscale VPN | Private access to your k3s node |

---

## How to use this documentation

Read in this order the first time:

1. [`learning-plan.md`](docs/learning-plan.md) — the roadmap and study sequence
2. [`domain-decomposition.md`](docs/domain-decomposition.md) — **start here**: turning the idea into entities & classes
3. [`phases.md`](docs/phases.md) — what you build, in what order
4. [`architecture.md`](docs/architecture.md) — how the system fits together
5. [`architecture-patterns.md`](docs/architecture-patterns.md) — layered, clean/hexagonal, DDD, event-driven, CQRS, and resilience patterns
6. [`oop-principles.md`](docs/oop-principles.md) — SOLID, composition, encapsulation, and practical OO judgment
7. [`design-patterns.md`](docs/design-patterns.md) — creational, structural, behavioral, and domain patterns
8. [`system-design.md`](docs/system-design.md) — scale, reliability, consistency, availability, latency, and back-pressure
9. [`end-to-end-flow.md`](docs/end-to-end-flow.md) — **the whole system in one walkthrough**: one expense traced through every component, with the failure matrix
10. [`project-structure-guide.md`](docs/project-structure-guide.md) — how to decide and evolve the repo layout; no tree is prescribed
11. [`drf-jwt-guide.md`](docs/drf-jwt-guide.md) — DRF, authentication, JWT/OAuth hands-on
12. [`api-contracts-guide.md`](docs/api-contracts-guide.md) — how to design, generate, validate, and maintain OpenAPI contracts
13. [`postgres-guide.md`](docs/postgres-guide.md) — the overview: modeling, tuning, observability
14. [`postgres/`](docs/postgres/) — **Postgres internals deep-dive** (10 docs): MVCC, storage, indexes, WAL, replication, vacuum, locking, partitioning, backup, tuning
15. [`data-model.md`](docs/data-model.md) — the schema you'll converge on
16. [`event-flows.md`](docs/event-flows.md) — Kafka flows for expense → loan updates
17. [`kafka-guide.md`](docs/kafka-guide.md) — topics, partitions, retention, delivery
18. [`avro-guide.md`](docs/avro-guide.md) — how to design, evolve, validate, and govern Avro `.avsc` schemas
19. [`data-lifecycle.md`](docs/data-lifecycle.md) — records, events, cleanup, archival
20. [`infrastructure.md`](docs/infrastructure.md) — Terraform + k3s + Helm
21. [`nginx/`](docs/nginx/) — **NGINX deep-dive** (8 docs): architecture, reverse proxy, load balancing, rate limiting, ingress in k3s, caching, security, tuning
22. [`tls/`](docs/tls/) — **TLS deep-dive** (6 docs): how-it-works, certificates, verification, TLS 1.3, this-project topology, operations
23. [`rate-limiting.md`](docs/rate-limiting.md) — rate-limiting algorithms and where limiters live in the stack
24. [`observability.md`](docs/observability.md) — Datadog, Postgres, Kafka dashboards
25. [`checkpoints.md`](docs/checkpoints.md) — stop-and-verify gates
26. [`milestones.md`](docs/milestones.md) — the milestones to "production-shaped"

Then use [`design.md`](docs/design.md), [`runbooks.md`](docs/runbooks.md), and
[`glossary.md`](docs/glossary.md) as references while you build.

Each phase in [`phases.md`](docs/phases.md) links back to the doc that explains the
concepts, then tells you what to build. The checkpoints exist so you don't drift —
work through them honestly.

---

## The domain in one paragraph

You record **expenses** (what you spent, when, from which source, in which category).
Some expenses are paid through **credit sources** (cards, lines of credit, loans).
When such an expense is recorded, an event is published to Kafka; a background
**consumer** picks it up and updates the outstanding balance on the related
**loan/credit account**. Over time, expenses and balance updates accumulate as
**historical events** that get archived to PVC-backed storage. Dashboards show
spending by category/source, loan balances, and Kafka health (lag, throughput,
ingress/egress, latency).

---

## Project status

- [ ] Phase 0 — Environment & tooling (`uv`, `ruff`, Docker)
- [ ] Phase 1 — Django + DRF skeleton + OpenAPI
- [ ] Phase 2 — Postgres + SQLAlchemy + migrations
- [ ] Phase 3 — Auth (JWT + OAuth2)
- [ ] Phase 4 — Core domain: categories, sources, expenses
- [ ] Phase 5 — Loans/credit accounts + balance logic
- [ ] Phase 6 — Kafka producer + Avro schemas
- [ ] Phase 7 — Kafka consumer + loan updater
- [ ] Phase 8 — Historical event archival to PVC
- [ ] Phase 9 — Helm charts + k3s deploy
- [ ] Phase 10 — Terraform provisioning
- [ ] Phase 11 — NGINX ingress + rate limiting + Tailscale
- [ ] Phase 12 — Observability + dashboards + runbooks
- [ ] Phase 13 — Hardening + backup/restore + full teardown/rebuild

See [`milestones.md`](docs/milestones.md) for what "done" means at each stage.
