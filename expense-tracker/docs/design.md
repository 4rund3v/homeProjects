# Design Decisions Log

> The single place every non-obvious decision is recorded, with the alternatives and
> the reason. Fill this in **as you build**, phase by phase — not at the end. Each
> guide lists the decisions it expects you to record here.

**Format for each entry:** the decision · the alternatives considered · why you chose
it · what would make you revisit it. If you can't fill in "what would make you revisit
it," you haven't finished thinking about the decision.

---

## How to use this file

- Add a section per area as you reach its phase (don't pre-fill).
- Date each entry; supersede rather than delete (strike through + note the new
  decision), so you can see how your thinking evolved.
- Reference the guide that frames the decision.
- These entries are what you'll defend at each checkpoint
  ([`checkpoints.md`](checkpoints.md)).

---

## Tooling (Phase 0)

- **uv for env/deps** — alternatives: poetry, pip+venv, pdm. Why: speed + lockfile
  determinism. Revisit if: a tool your team already standardizes on.
- **ruff rule set** — which rules enabled and why. Revisit if: a rule fights a
  deliberate pattern.

## API & contracts (Phase 1, 5)

- **Code-first vs contract-first** — and the schema generator chosen.
- **OpenAPI version** (3.0 vs 3.1) and whether the YAML is committed or a build
  artifact.
- **Versioning & deprecation policy.**
- **Pagination** (cursor vs offset) and the shared list-response shape.
- **Error envelope** shape and the standard status codes.
- **How the UI client is generated** and how breaking changes are detected.

## Auth (Phase 3)

- **Auth library** and why.
- **Access/refresh token lifetimes.**
- **Refresh token storage & rotation policy.**
- **SPA token storage** (cookie vs localStorage) and the accepted trade-off.
- **Social provider(s)** and the login→JWT flow; confirming you're doing OIDC, not
  running an OAuth2 server.
- **Throttle rates** for login vs authenticated endpoints.

## Domain & structure (Phase 4)

- **Entity list** and which are value objects.
- **Invariants** and the single enforcement point for each.
- **The Card decision**: source-with-linked-loan vs separate entity — and the defense.
- **Module/app split** and one sentence per app on what it owns.
- **Where the UI sits** (monorepo sibling / separate repo / served by Django) and why.
- **Where infra lives** and the image-tag boundary.

## OOP, patterns & architecture (Phase 4)

- **Layering adopted** and the dependency-direction rule you enforce (does the domain
  import any framework?).
- **Ports/adapters introduced** (repository, publisher, deserializer) and the test each
  enables — and dependencies you deliberately did *not* port (YAGNI).
- **The aggregate boundary** (Loan + BalanceChanges) and its link to the Kafka key.
- **Patterns adopted** (Value Object, Domain Service, Outbox, Idempotent Consumer) and
  the problem each solves here.
- **Patterns deliberately skipped** (Abstract Factory, hand-rolled Singleton, full
  Repository/UoW on Django, Visitor) and the trigger that would make you revisit each.
- **Framework patterns relied on** instead of built (Template Method via generic views,
  Strategy via auth/permission classes, Decorator via middleware).
- **Architecture patterns deferred** (CQRS, Saga, Circuit Breaker, Strangler Fig) and
  the measurable problem that would make you adopt each.

## Data (Phase 2, 8)

- **ID strategy** (bigint vs uuid).
- **Money representation** and currency handling.
- **Enum vs lookup table** for kind fields.
- **Partitioning scheme** (key, range, which tables).
- **ON DELETE** behavior per FK.
- **Connection pooling** approach and how the PgBouncer transaction-mode caveats are
  handled.
- **Tuning settings chosen**, each with before/after measurements.
- **Retention policy table** (hot/warm/archive/delete per data type).
- **Archival format & location** and the verification method.
- **The reconciliation check**: query, schedule, alert threshold.
- **The rebuild-from-archive procedure** and its trigger.

## Events & streaming (Phase 6, 7)

- **Message key** (`loan_id`) and the ordering invariant it protects.
- **Delivery semantics** (at-least-once) and the idempotency key (`event_id`).
- **Producer `acks`/replication** and the single-node caveat.
- **Topic naming & versioning strategy.**
- **Partition count** per topic and why.
- **`cleanup.policy`** per topic (delete vs compact).
- **Retention per topic**, tied to the reprocessing window.
- **Event envelope** fields (including the correlation ID).
- **Schema registry** choice and compatibility mode per subject.
- **Where `.avsc` files live** and how CI registers/validates them.

## Infrastructure (Phase 9–11)

- **Terraform state backend** and protection.
- **Pinned providers** and versions.
- **What Terraform owns vs what Helm owns** (the boundary, explicit).
- **Namespace layout.**
- **Upstream charts used** (Postgres, Kafka, ingress, observability) and versions.
- **Image registry & tagging scheme.**
- **Ingress routing, TLS approach, rate-limit values.**
- **The single-node caveat** and what's intentionally degraded.

## Observability (Phase 12)

- **Datadog vs Grafana+Prometheus** (or both) and the data-sharing trade-off accepted.
- **Which pillars ship where** (esp. logs and PII).
- **The starter alert set** and thresholds.
- **Dashboard layout** (Kafka, Postgres, app, edge).
- **Whether/when tracing is added.**

## System design (cross-cutting, record as you decide)

- **Consistency posture** per path (strong in DB, eventual across async) and how it's
  communicated in the contract.
- **Availability posture** and the documented single-node limitation.
- **Durability settings** chosen (`acks`, `synchronous_commit`) and their cost.
- **Back-pressure design** (the outbox) and its observability (depth/age alerts).
- **The scaling axis** you'd hit first, and the plan for it.
- **The dials you set** (consistency/availability, latency/throughput,
  durability/speed) and *why* for each.

---

## Superseded decisions

> When you change a decision, don't delete the old one — strike it through, note the
> date, and add the new one. Watching your reasoning evolve is part of the learning.

- _(none yet)_
