# Glossary

> Short definitions for the terms used across the guides, in the context of *this*
> project. Not exhaustive — just enough to keep the docs self-contained.

---

**Aggregate / Aggregate Root (DDD)** — a cluster of objects kept consistent together,
entered through one root; here, Loan + its BalanceChanges, and the reason events are
keyed by `loan_id` ([`architecture-patterns.md`](architecture-patterns.md)).

**Anemic Domain Model** — entities that are pure data bags with all logic in services;
the OOP failure mode [`oop-principles.md`](oop-principles.md) warns against.

**At-least-once** — a delivery guarantee where a message may be processed more than
once but never lost. Made safe here by an idempotent consumer
([`kafka-guide.md`](kafka-guide.md) §3).

**At-most-once** — a message may be lost but never duplicated. Wrong for financial
state; right for metrics.

**Autovacuum** — Postgres's background process that reclaims dead tuples (from MVCC
updates/deletes) and refreshes planner statistics
([`postgres-guide.md`](postgres-guide.md) §4).

**Avro** — a binary serialization format with explicit schemas and evolution rules,
used for Kafka messages ([`avro-guide.md`](avro-guide.md)).

**Backward compatible** — a new schema can read data written by an old schema
([`avro-guide.md`](avro-guide.md) §5).

**Bloat** — unreclaimed dead tuples inflating a table; caused by deletes/updates
outrunning vacuum ([`postgres-guide.md`](postgres-guide.md) §1).

**Back-pressure** — how a system behaves when a consumer can't keep up; here, the
durable, observable outbox buffer plus consumer lag
([`system-design.md`](system-design.md)).

**Bounded context (DDD)** — a soft boundary around a subdomain with its own language;
here, each Django app ([`architecture-patterns.md`](architecture-patterns.md)).

**CAP theorem** — during a network partition, choose consistency or availability; the
"pick two" phrasing is a misquote ([`system-design.md`](system-design.md)).

**Circuit breaker** — stop hammering a failing dependency so it can recover; adopted
later at synchronous boundaries ([`architecture-patterns.md`](architecture-patterns.md)).

**Composition over inheritance** — assemble behavior from small objects rather than a
subtype tree ([`oop-principles.md`](oop-principles.md)).

**Coupling & cohesion** — how much changing one part forces changes elsewhere, and how
strongly related things belong together ([`system-design.md`](system-design.md)).

**CQRS** — separating the write model from the read model; the light version (a
reporting layer) may suffice ([`architecture-patterns.md`](architecture-patterns.md)).

**Cache hit ratio** — fraction of reads served from Postgres's buffer cache vs disk;
should be high on a warm system ([`postgres-guide.md`](postgres-guide.md) §5).

**CHECK constraint** — a database rule a row must satisfy (e.g. `amount > 0`); a cheap
place to enforce an invariant ([`data-model.md`](data-model.md)).

**Consumer group** — a set of Kafka consumers sharing a topic's partitions; the unit of
parallelism and of lag ([`kafka-guide.md`](kafka-guide.md) §7).

**Correlation ID** — an identifier propagated across services (and into the event
envelope) so one logical request can be followed end-to-end
([`observability.md`](observability.md) §9).

**Dead-letter topic (DLQ)** — where messages that repeatedly fail processing are sent,
so they don't stall the loop ([`event-flows.md`](event-flows.md) §2).

**Drift** — divergence between Terraform's recorded state and the actual cluster;
caused by out-of-band manual changes ([`infrastructure.md`](infrastructure.md) §8).

**Exactly-once** — no loss and no duplication; in Kafka this needs transactions. Here
we approximate it with at-least-once + idempotency.

**Domain Service** — behavior that coordinates several entities and belongs to none of
them; orchestrates without stealing an entity's rules
([`design-patterns.md`](design-patterns.md)).

**DRY** — every piece of *knowledge* has one home; about knowledge, not duplicated text
([`oop-principles.md`](oop-principles.md)).

**Event Sourcing** — storing events as the source of truth and deriving state by
folding; here, borrowed as the "balances are a rebuildable projection" lens
([`architecture-patterns.md`](architecture-patterns.md)).

**Eventual consistency** — reads converge to the latest write given time; the posture
across the async boundary, and it must be documented in the contract
([`system-design.md`](system-design.md)).

**Expand/contract** — a safe schema-migration pattern: add new, backfill, switch, then
remove old — never rename/drop in one step against live traffic
([`postgres-guide.md`](postgres-guide.md) §7).

**Forward compatible** — an old schema can read data written by a new schema
([`avro-guide.md`](avro-guide.md) §5).

**Hexagonal / Ports & Adapters** — the domain at the center, externals plugged in
through ports it defines; adopt the spirit, skip the ceremony
([`architecture-patterns.md`](architecture-patterns.md)).

**Idempotency key** — a value (`event_id`) that makes applying an operation twice a
no-op; enforced by a DB unique constraint ([`kafka-guide.md`](kafka-guide.md) §3).

**Interface Segregation** — many small interfaces beat one fat one; often moot in
Python's duck-typed world ([`oop-principles.md`](oop-principles.md)).

**Invariant** — a rule the domain must never violate; each maps to exactly one
enforcement point ([`domain-decomposition.md`](domain-decomposition.md) §3).

**Liskov Substitution** — a subtype must be usable wherever its base type is; the test
the Card-as-Source decision must pass ([`oop-principles.md`](oop-principles.md)).

**Ingress** — the Kubernetes resource + controller that routes external HTTP(S) traffic
into services; here, NGINX ([`infrastructure.md`](infrastructure.md) §5).

**JWT** — a signed, stateless token carrying claims; used for API auth
([`drf-jwt-guide.md`](drf-jwt-guide.md) §4).

**k3s** — a lightweight, single-binary Kubernetes distribution for the edge
([`infrastructure.md`](infrastructure.md) §3).

**Kafka / KRaft** — the event-streaming platform; KRaft is its ZooKeeper-less
consensus mode ([`kafka-guide.md`](kafka-guide.md) §8).

**Lag** — the gap between a partition's latest offset and a consumer group's committed
offset; the #1 Kafka health signal ([`kafka-guide.md`](kafka-guide.md) §7).

**Lockfile** (`uv.lock`) — the pinned, resolved dependency set that makes builds
reproducible ([`learning-plan.md`](learning-plan.md)).

**MTTR / MTBF** — mean-time-to-recovery vs mean-time-between-failures; reliability work
mostly drives MTTR down via runbooks and rollbacks
([`system-design.md`](system-design.md)).

**MVCC** — multiversion concurrency control; readers don't block writers, at the cost
of dead tuples ([`postgres-guide.md`](postgres-guide.md) §1).

**Offset** — a consumer's position in a partition; committing it marks progress and
determines delivery semantics ([`kafka-guide.md`](kafka-guide.md) §1).

**OIDC / social login** — delegating identity to a provider, then issuing your own
token; distinct from running your own OAuth2 server
([`drf-jwt-guide.md`](drf-jwt-guide.md) §3).

**Open/Closed Principle** — open for extension, closed for modification; extend on the
second case, not the first ([`oop-principles.md`](oop-principles.md)).

**OpenAPI** — the standard description format for REST APIs; the UI↔API contract
([`api-contracts-guide.md`](api-contracts-guide.md)).

**Outbox (transactional)** — a table written in the same transaction as the domain
change; a relay publishes its rows to Kafka, giving DB↔Kafka atomicity without
distributed transactions ([`event-flows.md`](event-flows.md)).

**PACELC** — the fuller framing of CAP: during a partition pick A or C, else trade
latency for consistency ([`system-design.md`](system-design.md)).

**Partition (Kafka)** — a subdivision of a topic; ordering is guaranteed only within
one, so the key determines correctness ([`kafka-guide.md`](kafka-guide.md) §2).

**Partition (Postgres)** — a table split by range (e.g. by month), making archival and
cleanup cheap ([`postgres-guide.md`](postgres-guide.md) §6).

**PgBouncer** — a connection pooler in front of Postgres, so many app connections map
to few real ones ([`postgres-guide.md`](postgres-guide.md) §4).

**Projection** — a read-optimized value derived from an event log (e.g. a loan's
`outstanding` balance) that can be rebuilt by replay
([`data-lifecycle.md`](data-lifecycle.md) §5).

**PVC / PV** — persistent storage in Kubernetes that survives pod restarts; holds DB
data and archives ([`infrastructure.md`](infrastructure.md) §3).

**Reconciliation** — a scheduled check that derived state matches its source of truth
(e.g. balances match the event sum); the drift detector and rebuild trigger
([`data-lifecycle.md`](data-lifecycle.md) §5).

**RED method** — Rate, Errors, Duration; how to instrument a service
([`observability.md`](observability.md) §3).

**Repository** — an abstraction over persistence so the domain is testable without a
DB; keep it thin on top of Django's ORM ([`design-patterns.md`](design-patterns.md)).

**Retention** — how long Kafka keeps messages (time/size/compaction); a per-topic
policy tied to your reprocessing window ([`kafka-guide.md`](kafka-guide.md) §6).

**Saga** — a multi-step process across services with compensating rollbacks; choreography
vs orchestration; deferred here ([`architecture-patterns.md`](architecture-patterns.md)).

**Schema registry** — the versioned store of Avro schemas that enforces compatibility
on registration ([`avro-guide.md`](avro-guide.md) §2).

**Single Responsibility** — one reason to change per class; about reasons, not line
counts ([`oop-principles.md`](oop-principles.md)).

**SOLID** — the five OO principles (SRP, OCP, LSP, ISP, DIP); DIP is the most valuable
here because it makes the domain testable
([`oop-principles.md`](oop-principles.md)).

**StatefulSet** — the Kubernetes primitive for stateful workloads with stable identity
and storage; used for Postgres and Kafka ([`infrastructure.md`](infrastructure.md) §3).

**Strangler Fig** — replacing part of a running system incrementally behind a facade;
the antidote to big-bang rewrites
([`architecture-patterns.md`](architecture-patterns.md)).

**Tailscale** — an encrypted mesh VPN giving private access to your node without
exposing ports publicly ([`infrastructure.md`](infrastructure.md) §5).

**Terraform** — declarative infrastructure-as-code with a plan/apply/state loop; your
main learning-curve area ([`infrastructure.md`](infrastructure.md) §2).

**Throttling vs rate limiting** — DRF throttling is per-user and semantic; NGINX rate
limiting is per-IP and coarse; use both ([`drf-jwt-guide.md`](drf-jwt-guide.md) §6).

**Transactional outbox** — see **Outbox (transactional)**.

**Unit of Work** — coordinating several changes into one transaction; in Django this is
`transaction.atomic()`, not a hand-rolled class
([`design-patterns.md`](design-patterns.md)).

**Value object** — a type defined by its values with no identity (e.g. `Money`); the
cheapest high-leverage modeling move
([`domain-decomposition.md`](domain-decomposition.md) §3).

**YAGNI** — don't build for hypothetical futures; make code easy to refactor instead of
pre-building abstractions ([`oop-principles.md`](oop-principles.md)).

**uv** — a fast Python package/environment manager built around a lockfile for
reproducibility ([`learning-plan.md`](learning-plan.md)).
