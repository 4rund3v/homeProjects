# Architecture Patterns

> The system-level shapes — layered, clean/hexagonal, DDD, CQRS, event-driven, and the
> reliability patterns (saga, circuit breaker, back-pressure). Each mapped to **what
> shape this project should take, per phase**, and what to adopt later. Object-level
> design is in [`oop-principles.md`](oop-principles.md) and
> [`design-patterns.md`](design-patterns.md); the concrete system is in
> [`architecture.md`](architecture.md).

---

## How to read this

An architecture pattern is a **way of arranging boundaries** in a system. Every
boundary buys you something (independent change, testability, scaling) and costs you
something (indirection, files, ceremony). The judgment is: *which boundaries earn their
cost at my current scale?*

The through-line below: **start with a thin layered shape, keep the domain layer clean
(hexagonal in spirit, not in ceremony), let event-driven handle the async path, and add
CQRS/saga/breakers only when a specific problem forces it.**

---

## Layered architecture

**Shape:** presentation → application/service → domain → infrastructure, with
dependencies pointing **inward** (upper layers depend on lower abstractions, not the
reverse).

```
   Presentation   (DRF views, serializers)      ← HTTP in/out
        ↓
   Application    (services, orchestration)     ← use cases
        ↓
   Domain         (entities, value objects,
                   invariants)                  ← business rules, no frameworks
        ↓
   Infrastructure (ORM, Kafka, settings)        ← details, injected inward
```

**Here — yes, this is your baseline.** It's the shape implied by
[`domain-decomposition.md`](domain-decomposition.md) and
[`project-structure-guide.md`](project-structure-guide.md): thin views, services that
orchestrate, a domain layer that imports neither HTTP nor Kafka, infrastructure injected
from the edges.

**The one rule that makes it real:** the **domain layer imports nothing from Django
request/response, Kafka, or the ORM's query internals.** If your `Loan` knows what a
serializer is, the layering is decorative. This is what lets you test the balance rule
with no database ([`oop-principles.md`](oop-principles.md), DIP).

**Cost:** one extra hop (view → service → entity). Worth it the moment business rules
exist — which is immediately, here.

---

## Clean / Hexagonal (Ports & Adapters)

**Shape:** the domain sits at the center, untouched. Everything external plugs in
through **ports** (interfaces the domain defines) and **adapters** (implementations:
Postgres adapter, Kafka adapter, HTTP adapter).

```
        HTTP adapter ──┐
                        ├──→  [ PORT ] ──→  DOMAIN  ──→ [ PORT ] ──┬──→ Postgres adapter
   Kafka adapter ──────┘    (driven by                           (driving)  └──→ Kafka adapter
                             the app)                                    └──→ Schema registry adapter
```

**Here — adopt the *spirit*, skip the ceremony.** The valuable idea: **the domain
defines the interfaces it needs (a repository port, a publisher port), and concrete
adapters satisfy them.** That's what makes the domain testable with fakes. The
ceremony to skip: a formal ports/adapters package structure with an interface class per
operation. In Python, a plain abstract base or `Protocol` at the boundary is enough.

**How it shows up here:**
- The relay depends on a `Publisher` port; the Kafka adapter implements it — so you can
  test the relay with a fake publisher.
- The consumer depends on a `Deserializer` port; the Avro/registry adapter implements it.
- Services depend on repository ports, not SQLAlchemy imports.

**Cost/benefit:** the ports are worth it exactly where the external dependency is
awkward in tests (Kafka, the registry). For a simple Postgres read, a plain queryset is
honest — don't port everything reflexively (ties to YAGNI,
[`oop-principles.md`](oop-principles.md)).

---

## Domain-Driven Design (DDD)

**Shape:** model the domain deeply — **entities, value objects, aggregates, domain
events, repositories, domain services** — organized into **bounded contexts** with a
**ubiquitous language**.

**Here — adopt the tactical patterns, use a lightweight bounded-context view.** You're
already doing the core of DDD via [`domain-decomposition.md`](domain-decomposition.md)
and [`design-patterns.md`](design-patterns.md):

| DDD concept | In this project |
|-------------|-----------------|
| Entity | Expense, Loan, Category ([`data-model.md`](data-model.md)) |
| Value Object | `Money` |
| Aggregate + Root | Loan + its BalanceChanges; invariant "sum = outstanding" |
| Domain Event | `ExpenseRecorded` ([`avro-guide.md`](avro-guide.md)) |
| Domain Service | `ExpenseService`, `LoanService` |
| Repository | thin, where it buys testability |
| Bounded Context | your Django apps (expenses, loans, categories) |
| Ubiquitous Language | the terms in [`glossary.md`](glossary.md) |

**Bounded contexts, honestly:** you don't need formal context mapping or anti-corruption
layers for a personal tracker. Treat each Django app as a soft bounded context — its own
language, its own models, depending on others only through public interfaces
([`project-structure-guide.md`](project-structure-guide.md) §2). That's the useful 20%
of DDD without the 80% of formalism.

**The highest-value DDD idea for you:** the **aggregate defines the unit of consistency
and therefore the Kafka key** ([`kafka-guide.md`](kafka-guide.md) §2). Get the aggregate
boundary right and the partitioning, ordering, and idempotency decisions follow.

---

## Event-Driven Architecture

**Shape:** components communicate by emitting and reacting to **events** rather than
calling each other directly. Producers don't know consumers.

**Here — yes, for the async path.** This is exactly the expense→loan flow: the API
publishes `ExpenseRecorded` via the outbox; the consumer reacts. The API doesn't know
the consumer exists, which is what makes each side independently deployable
([`architecture.md`](architecture.md) §3).

**The patterns that make event-driven trustworthy here:**
- **Transactional outbox** — atomic DB + event ([`event-flows.md`](event-flows.md) §2).
- **Idempotent consumer** — safe at-least-once ([`kafka-guide.md`](kafka-guide.md) §3).
- **Event as source of truth** — balances are projections; rebuild by replay
  ([`data-lifecycle.md`](data-lifecycle.md) §5).
- **Schema registry + compatibility** — producers and consumers evolve independently
  ([`avro-guide.md`](avro-guide.md) §5).

**Cost:** eventual consistency (the loan balance lags the expense by a moment) and
operational surface (lag, DLQ, retention). Both are documented in
[`observability.md`](observability.md) and [`runbooks.md`](runbooks.md). **The
contract must be honest about the async window** ([`api-contracts-guide.md`](api-contracts-guide.md)
§5).

---

## CQRS (Command Query Responsibility Segregation)

**Shape:** separate the **write model** (commands that change state) from the **read
model** (queries optimized for display), often with the read side built from events.

**Here — adopt the *light* version, defer the formal one.** You already have an
asymmetry worth respecting: writes go through the expense/loan aggregate; reads are
reporting queries over expenses. The pragmatic move is a **separate read path** — a
reporting service and/or a materialized summary table ([`postgres-guide.md`](postgres-guide.md)
§2) — without splitting into two models with separate databases.

**Adopt full CQRS when:** a read pattern genuinely doesn't fit the write model (e.g.
complex cross-entity dashboards slowing the write path), and you've *measured* it. Until
then, one model with a dedicated read/reporting layer is simpler and honest.

**Trap:** CQRS is the most over-applied architecture pattern. It adds a second model, a
synchronization mechanism, and eventual-consistency reasoning. Don't adopt it for a
dashboard you could serve with one indexed query.

---

## Event Sourcing

**Shape:** store the **sequence of events** as the source of truth; derive current state
by folding over them.

**Here — borrow the lens, don't commit fully.** The useful idea: *your
`balance_changes` are the truth; `loans.outstanding` is a projection you can rebuild*
([`data-lifecycle.md`](data-lifecycle.md) §5). That framing gives you free disaster
recovery — replay to rebuild. You get this **without** making events the sole store for
everything (expenses stay as regular records).

**Full event sourcing** (events as the only store, everything derived) is a larger
commit: schema evolution of the event log becomes critical, queries need projections for
everything, and reasoning gets harder. Learn it; apply the *rebuild-from-events*
capability here without the full conversion.

---

## Saga (distributed transactions)

**Problem:** a business process spans multiple services/steps; if a later step fails,
earlier steps must be compensated.

**Here — not yet.** Your two-step flow (record expense → update loan) is made reliable
by the **outbox + idempotent consumer**, not a saga — there's no multi-service rollback
to coordinate. A saga becomes relevant if you later add, say, "record expense → update
loan → notify → update budget" across services with real compensations.

**Know two forms for later:** **choreography** (each service reacts to events, no
coordinator — what you have in miniature) and **orchestration** (a central coordinator
drives the steps and issues compensations). Prefer choreography until coordination
complexity forces an orchestrator.

---

## Circuit Breaker & resilience

**Problem:** a slow/failing dependency (OAuth provider, schema registry) shouldn't
exhaust your workers or cascade into a full outage.

**Here — later, at synchronous boundaries.** Your Kafka path already degrades gracefully
(failures queue in the outbox rather than cascade,
[`event-flows.md`](event-flows.md) §5). Add an explicit **circuit breaker** when the API
gains a *synchronous* external call that can hang (e.g. calling an OAuth provider on
every login). Pair it with **timeouts** and **retries with backoff** — a retry without a
timeout is just a slower failure.

**Back-pressure** is the streaming-side cousin: when consumers fall behind, don't buffer
infinitely — that's what **consumer lag** signals, and why you alert on it
([`observability.md`](observability.md) §5). Your producers already apply back-pressure by
being durable-first (outbox) rather than fire-and-forget.

---

## Strangler Fig (for evolving systems)

**Problem:** you need to replace part of a running system without a big-bang rewrite.
**Here — not now, but it's your future tool.** If you ever migrate this app (new
framework, new schema), the pattern is: put a facade in front, route new behavior to the
new implementation incrementally, retire the old piece by piece. Relevant if you rebuild
the UI or swap the ORM later. Keep it in the back pocket; it's the antidote to
rewrite-itis.

---

## What shape this project takes, per phase

| Phase | Architecture stance |
|-------|---------------------|
| 1–2 | **Layered**, minimally: view → service → ORM. Get the dependency direction right. |
| 3–5 | **Layered + clean domain in spirit:** domain imports no HTTP/ORM; thin repository ports where they buy testability. |
| 4 | **Soft bounded contexts** = Django apps; depend across apps only via public interfaces. |
| 6–7 | **Event-driven** on the async path: outbox + idempotent consumer + schema registry. |
| 8 | **Event-sourcing lens** for loans: balances are projections; rebuild by replay. |
| 5+ | **Light CQRS** if a read path needs it: a reporting layer, measured before adding. |
| later | **Saga / circuit breaker / strangler fig** only when a specific problem forces them. |

**The trajectory:** each pattern is adopted *in response to a problem*, in the phase
where that problem appears — never pre-emptively. That's the discipline that keeps the
architecture comprehensible.

---

## The boundaries that must survive (regardless of pattern)

Whatever shapes you adopt, these boundaries from
[`architecture.md`](architecture.md) §6 are load-bearing:

- **UI ↔ API:** OpenAPI contract only.
- **API ↔ domain:** thin views; services own rules.
- **API ↔ Kafka:** transactional outbox.
- **Producer ↔ consumer:** Avro + registry.
- **Consumer ↔ Postgres:** idempotency key.
- **App ↔ infra:** image tags, not source paths.
- **Hot ↔ cold data:** partitioning + archival policy.

Protect these and the architecture stays comprehensible as it grows.

---

## Checkpoint questions

- Draw your layers and show the **dependency direction**. Does the domain import any
  framework?
- Where does the domain define a **port**, and what **adapter** satisfies it? Which
  dependency did you *not* port, and why (YAGNI)?
- What's your **aggregate**, and how does it determine the Kafka key?
- Is the loan balance a **projection**? Show how you'd rebuild it.
- Which architecture pattern did you **defer**, and what measurable problem would make
  you adopt it?
- How is the **eventual-consistency window** communicated in the API contract?

---

## Decisions to record in `design.md`

- The layering you adopted and the dependency-direction rule you enforce.
- Which ports/adapters you introduced, and the test each enables.
- Your aggregate boundary and its link to the Kafka key.
- Whether balances are a rebuildable projection (yes) and the rebuild procedure.
- The architecture patterns deliberately deferred, and their adoption triggers.
