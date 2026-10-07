# Kafka Basics

**Goal:** Learn event-streaming behavior with a small local Kafka-compatible KRaft setup.

**Scope:** Producer/consumer, topics, partitions, keys, consumer groups, offsets, lag, delivery guarantees, optional schema registry.

**Out of scope:** Multi-cluster operations, large-scale production tuning, and assuming exactly-once behavior without end-to-end analysis.

**Learning focus:** Partition ordering, rebalances, offset commits, retries, idempotency, and delivery semantics.

**Depends on:** `go-fundamentals`, `python-refresh`; compare with `redis-cache`.

## Milestones
- [ ] Produce from Go and consume from Python in one partition.
- [ ] Add a second consumer; inspect group assignment and rebalances.
- [ ] Demonstrate duplicate delivery and make processing idempotent.
- [ ] Measure consumer lag; optionally feed events into `telemetry-hub`.

**Environment (Python consumer):** See [`uv-setup.md`](../uv-setup.md).
