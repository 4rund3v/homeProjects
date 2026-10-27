# Design Patterns

> **Deep-dive versions live in [`design-patterns/`](design-patterns/)** — one doc each
> for DDD-tactical, creational, structural, behavioral, and reliability patterns, with
> worked examples on this codebase and interview angles. This file is the one-page
> overview / index. Read the folder for L5/L6 depth.
>
> The patterns worth knowing, each mapped to **whether it applies to this project** —
> and when it's a trap. No code; the intent, the shape, and the judgment call. Patterns
> follow from the principles in [`oop-principles.md`](oop-principles.md); the
> system-level shapes are in [`architecture-patterns.md`](architecture-patterns.md).

---

## How to read this

A pattern is a **named solution to a recurring problem in a context**. The two words
that matter are *problem* and *context*. A pattern applied without its problem is just
ceremony. So each entry below states the problem it solves, then whether that problem
exists here.

**The rule:** learn the pattern, recognize the problem, *then* reach for it. Never
start from the pattern.

---

## A word on Django/DRF

Several classic patterns are **partly built into Django/DRF** — recognizing where the
framework already implements a pattern is as valuable as implementing one yourself:

| Pattern | Where DRF/Django gives it to you |
|---------|----------------------------------|
| Template Method | Generic class-based views / `ViewSet` hooks |
| Factory | `get_serializer_class()`, `get_queryset()` |
| Front Controller | URL routing → one entry point |
| Active Record (partly) | Django ORM models |
| Decorator | `@permission_classes`, `@throttle_classes`, middleware |
| Strategy | Authentication/permission *classes* swapped per view |

So the question isn't "which patterns do I build" but "which does the framework handle,
which do I add, and where does the framework's choice constrain me?"

---

## Creational — how objects get made

### Factory Method / Simple Factory
**Problem:** object creation is complex or varies by type, and you don't want callers
coupled to concrete classes.
**Here — yes, lightly.** Creating a `Money(amount, currency)` from raw input, or
building the right event payload per event type, is a natural factory spot. DRF's
`get_serializer_class()` is a factory you already use.
**Trap:** a factory that returns one type, forever. If there's exactly one product, a
constructor call is simpler.

### Builder
**Problem:** an object has many optional parts and constructor arguments become
unreadable.
**Here — rarely.** Most of your objects are small. Reserve it for genuinely
many-parameter construction (e.g. a complex Kafka producer config), and prefer keyword
arguments or a config dataclass first.

### Singleton
**Problem:** exactly one instance, globally accessible.
**Here — mostly avoid.** Singletons hide dependencies and wreck testability. Where you
want "one" (a DB engine, a Kafka producer), use **dependency injection** of a single
shared instance managed at the app boundary — not a global. Note: Django settings and
the ORM connection are effectively managed singletons already; don't add more.

---

## Structural — how objects compose

### Adapter
**Problem:** two incompatible interfaces must work together.
**Here — yes.** Wrapping a third-party OAuth provider's token response into your own
`Identity` shape; adapting the schema-registry client into a clean `serialize/deserialize`
interface for your relay and consumer. This is DIP ([`oop-principles.md`](oop-principles.md))
made concrete.

### Decorator
**Problem:** add behavior to an object without subclassing or editing it.
**Here — yes, heavily, via the framework.** `@permission_classes`, throttling, and
middleware are decorators. Python's own decorators wrap functions. Recognize it; use the
framework's version rather than rolling your own.

### Facade
**Problem:** a subsystem is complex; callers need one simple entry point.
**Here — yes.** A `LedgerFacade` / service that exposes "record an expense" and hides
the expense insert + outbox write + validation coordination
([`event-flows.md`](event-flows.md) §1). Keep the facade thin — it coordinates, it
doesn't accumulate all logic (that's the God-object trap).

### Repository
**Problem:** domain logic shouldn't know about SQL/ORM specifics.
**Here — yes, but measure it.** A repository abstracts persistence so the domain is
testable without a DB (DIP). **Caveat for Django:** the ORM is already an abstraction,
and Django's Active Record style means models *are* the persistence layer. A full
Repository + Unit of Work stack on top of Django can be ceremony. Pragmatic middle
ground: keep query logic in a thin per-app repository/queryset module so services don't
scatter ORM calls, and inject it where you need to fake persistence in tests. Don't
build a Hibernate-style layer.

### Unit of Work
**Problem:** coordinate several changes into one atomic transaction.
**Here — yes, via transactions, not a hand-rolled UoW.** Django's
`transaction.atomic()` *is* the Unit of Work for the expense-insert + outbox-write
([`event-flows.md`](event-flows.md) §1), and for the consumer's balance-change +
outstanding-update (§3). Use the framework's transaction; don't implement a UoW class
unless you outgrow it.

---

## Behavioral — how objects interact

### Strategy
**Problem:** several interchangeable ways to do one thing, chosen at runtime.
**Here — yes.** Authentication classes, permission classes, and throttling in DRF are
Strategy. A future "how to compute spend summary" could have strategies (this month vs
this year). Choose the strategy, swap the behavior.

### Observer / Publish-Subscribe
**Problem:** one thing happens; several unrelated things should react, without the
source knowing them.
**Here — yes, and it's the heart of your system.** Kafka *is* a distributed
Observer/Pub-Sub. The producer (via outbox) publishes `ExpenseRecorded`; the consumer
observes it and updates the loan — without the API knowing a consumer exists
([`architecture.md`](architecture.md) §3). Recognize that your event bus is this
pattern at scale.

### Command
**Problem:** encapsulate a request as an object, so it can be queued, logged, retried,
or undone.
**Here — partially.** Your **outbox rows are effectively serialized Commands/Events**:
they're queued and retried by the relay. And the consumer processing an event is
executing a command idempotently. You don't need a formal Command class hierarchy — the
outbox row + Avro event already play the role. Recognize it; don't ceremonially wrap it.

### Template Method
**Problem:** an algorithm's skeleton is fixed; steps vary.
**Here — via the framework.** DRF generic views define the skeleton
(`validate → perform_create → serialize`), you override steps. Also useful for your
consumer loop: the skeleton (consume → deserialize → idempotency-check → apply → commit)
is fixed; the "apply" step varies by event type.

### Saga (distributed, behavioral)
**Problem:** a multi-step business process spans services; if one step fails, undo the
others.
**Here — not yet, but know it.** You have a two-step flow (record expense → update
loan) made reliable by the **transactional outbox** rather than a saga
([`event-flows.md`](event-flows.md)). A full saga (with compensating transactions)
becomes relevant if you later add multi-step processes across services. Learn the
concept; you don't need the machinery now.

### Circuit Breaker
**Problem:** a failing dependency shouldn't be hammermed into total collapse.
**Here — later, at the edges.** When the API calls external things (OAuth provider,
schema registry), a circuit breaker prevents a slow dependency from exhausting your
workers. Your Kafka path already degrades gracefully via the outbox (failures queue,
don't cascade). Add an explicit breaker when you have a synchronous external dependency
that can hang.

---

## Domain patterns (the ones that matter most for your modeling)

### Value Object
**Problem:** a concept defined by its values, with rules, that shouldn't be a loose bag
of fields.
**Here — yes, high value.** `Money(amount, currency)` with "positive" and "currency
must match" enforced in one place. This is the single cheapest, highest-leverage
modeling move in the project ([`domain-decomposition.md`](domain-decomposition.md) §3).

### Entity
**Problem:** something with a persistent identity that lives over time, distinct from
its current attribute values.
**Here — yes.** `Expense`, `Loan`, `Category` have identity (their `id`); two expenses
with identical amounts are still two expenses. Contrast with `Money`, which has no
identity — same values means same money.

### Aggregate + Aggregate Root (DDD)
**Problem:** a cluster of objects that must be consistent together; you need one entry
point that guards the whole cluster's invariants.
**Here — yes, and it drives your Kafka key.** The **Loan + its BalanceChanges** form an
aggregate: the invariant "sum of changes = outstanding" spans them, so the Loan is the
aggregate root and the only way in. This is *why* you key events by `loan_id`
([`kafka-guide.md`](kafka-guide.md) §2) — the aggregate is the unit of consistency
*and* the unit of ordering.

### Domain Service
**Problem:** behavior that doesn't belong to any single entity because it coordinates
several.
**Here — yes.** `ExpenseService.record` coordinates validation + persistence + outbox;
`LoanService.apply_expense` coordinates the loan + the balance change. **Rule:** the
service *orchestrates*; the entity enforces its own invariants. A service that reaches
into an entity's fields to enforce a rule has the logic in the wrong place
([`oop-principles.md`](oop-principles.md), "Tell, Don't Ask").

### Domain Event
**Problem:** something that happened in the domain that other parts of the system care
about.
**Here — yes, central.** `ExpenseRecorded` is a domain event: an immutable fact,
published via the outbox, consumed to update state. Model events as **facts (past
tense)**, not commands ([`avro-guide.md`](avro-guide.md) §3).

### Transactional Outbox
**Problem:** you must update the database and publish an event atomically, without a
distributed transaction.
**Here — yes, this is your core reliability pattern.** Write the event to an outbox
table in the same DB transaction as the expense; a relay publishes it
([`event-flows.md`](event-flows.md) §2). This one pattern is what makes the whole async
flow trustworthy.

### Idempotent Consumer
**Problem:** at-least-once delivery means duplicates; applying twice corrupts state.
**Here — yes.** The consumer deduplicates on `event_id`, enforced by a DB unique
constraint ([`kafka-guide.md`](kafka-guide.md) §3). This is what makes "replay to
rebuild" safe ([`data-lifecycle.md`](data-lifecycle.md) §5).

---

## Patterns to consciously NOT use (and why)

Knowing what to skip is as important as knowing what to apply.

| Pattern | Why skip it here |
|---------|------------------|
| **Abstract Factory** | you have one product family, not several |
| **Full Repository + UoW on Django** | the ORM + `transaction.atomic()` already do it; a parallel layer is ceremony |
| **Singleton (hand-rolled)** | hides dependencies, breaks tests; use DI instead |
| **Visitor** | adds a class per operation over a stable structure you don't have |
| **Interpreter** | no mini-language to parse |
| **MVC (strictly)** | you're doing a thin-view + service + domain layering; DRF isn't classic MVC |
| **Microservices + full Saga now** | one deployable is correct at this scale; split when forced |

---

## The pattern-selection discipline

Before adopting any pattern, answer:

1. **What problem do I have right now** that this solves? (If none — skip it.)
2. **What's the simplest thing** that could work? Can I do that instead?
3. **What does the framework already give me?** (Often the pattern is built in.)
4. **What will this cost** in indirection, files, and learning overhead?
5. **When would I remove it?** (If never, it might be load-bearing; if "immediately,"
   it's speculative.)

Record the patterns you adopt — and the ones you deliberately skip — in
[`design.md`](design.md). "We considered a Repository layer and skipped it because the
ORM suffices" is a valuable design note.

---

## Checkpoint questions

- Which patterns does **DRF already implement** for you, and where?
- Name the **aggregate** in your domain and the invariant that defines its boundary.
- Why is `Money` a Value Object and `Expense` an Entity?
- What makes your consumer **idempotent**, and is that enforced in code or the database?
- Where does a **Domain Service** orchestrate without stealing an entity's rules?
- Which pattern did you **decide not to use**, and what would have to change to
  reconsider?

---

## Decisions to record in `design.md`

- The aggregate boundary (Loan + BalanceChanges) and why.
- Whether you add a repository/queryset layer, and how thin.
- Which framework-provided patterns you rely on instead of building.
- The patterns deliberately skipped, and the trigger that would make you revisit each.
