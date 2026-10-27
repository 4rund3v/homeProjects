# Architecture Patterns — Deep Dives

> The companion folder to the overview in [`../architecture-patterns.md`](../architecture-patterns.md).
> The overview tells you *which* architecture this project should take, per phase.
> This folder goes deep on the individual architectures and the resilience patterns
> that make them trustworthy — the L5/L6 material.

## The files

| File | Covers |
|------|--------|
| [`layered.md`](layered.md) | Classic n-tier / layered: the baseline shape, the dependency-direction rule, and where the layers leak |
| [`hexagonal.md`](hexagonal.md) | Ports & Adapters: what's worth it vs what's ceremony in a Django/DRF codebase |
| [`ddd-strategic.md`](ddd-strategic.md) | Bounded contexts, context mapping, ubiquitous language — the *strategic* side of DDD (tactical patterns live in `design-patterns/ddd-tactical.md`) |
| [`event-driven.md`](event-driven.md) | Event-driven architecture end to end: topics, outbox, consumer groups, schema evolution, and the consistency model |
| [`resilience.md`](resilience.md) | Timeouts, retries with backoff, circuit breakers, bulkheads, rate limiting, load shedding, fallbacks — the resilience toolbox, each with where it's used here |

## How to use it

- **"What architecture should I use for a new service?"** → read [`layered.md`](layered.md) +
  [`hexagonal.md`](hexagonal.md) for the shape, [`event-driven.md`](event-driven.md) for the
  async path.
- **"My domain is growing and things are entangling"** → [`ddd-strategic.md`](ddd-strategic.md).
- **"What do I do when a dependency is slow or flaky?"** → [`resilience.md`](resilience.md).

Cross-references: object-level patterns in [`../design-patterns/`](../design-patterns/),
the OOP principles in [`../oop-principles.md`](../oop-principles.md), the concrete
system in [`../architecture.md`](../architecture.md), the system-design concepts
(scalability, CAP, etc.) in [`../system-design/`](../system-design/).
