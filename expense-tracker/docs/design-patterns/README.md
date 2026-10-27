# Design Patterns — Deep Dives

> The companion folder to the overview in [`../design-patterns.md`](../design-patterns.md).
> The overview tells you *whether* a pattern applies here and why. This folder goes
> deeper on the individual patterns, with worked examples on this project's code and the
> interview angles that actually get asked. Each file follows the same shape:
> **the problem → the pattern → a concrete example on this codebase → the trade-off →
> how to explain it in an interview.**

These are written for **L5/L6 prep**, so assume you'll be asked to *justify* a pattern
choice or explain why a framework already does it for you, not just name it.

## The files

| File | Covers |
|------|--------|
| [`ddd-tactical.md`](ddd-tactical.md) | Entity, Value Object, Aggregate, Domain Service, Domain Event, Repository, Specification — the DDD tactical patterns, each mapped to `Money`, `Loan`, `Expense` |
| [`creational.md`](creational.md) | Factory, Builder, Abstract Factory, Singleton — when each is worth it on a Django/DRF codebase, when they're ceremony |
| [`structural.md`](structural.md) | Adapter, Decorator, Facade, Proxy, Composite — the Django/DRF instances you already use without realizing it |
| [`behavioral.md`](behavioral.md) | Strategy, Observer/Pub-Sub, Command, Template Method, Chain of Responsibility, Mediator — and which ones DRF or Kafka already implement |
| [`reliability-patterns.md`](reliability-patterns.md) | Transactional Outbox, Idempotent Consumer, Saga, Circuit Breaker, Caching, Bulkhead, Timeouts & Retries — the reliability patterns this project depends on |

## How to use it

- **For a specific pattern** you're unsure about: go straight to that file.
- **For "explain the aggregate in my domain"**: start with [`ddd-tactical.md`](ddd-tactical.md).
- **For "why is the outbox the right choice"**: [`reliability-patterns.md`](reliability-patterns.md`).
- **For the "is this pattern worth the ceremony" judgment calls**: every file ends with a
  "when to skip it" section — that's the L5/L6 discriminator.

Cross-references: the OOP principles these patterns follow live in
[`../oop-principles.md`](../oop-principles.md); the system-level shapes that group these
into architectures are in [`../architecture-patterns/`](../architecture-patterns/).
