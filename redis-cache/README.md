# Redis Cache and Streams

**Goal:** Compare Redis caching and stream-processing semantics from both Go and Python clients.

**Scope:** Cache-aside, TTLs, invalidation, basic pub/sub, Redis Streams consumer groups, local Redis instance.

**Out of scope:** Redis Cluster/Sentinel operations and using Redis as a durable database.

**Learning focus:** Cache correctness, stampedes, idempotency, delivery/acknowledgment semantics, backpressure, operational failure modes.

**Depends on:** `go-fundamentals`, `python-refresh`; optionally `drf-basics` for a real endpoint.

## Milestones
- [ ] Add cache-aside to one API endpoint and test expiry/invalidation.
- [ ] Publish in Go and subscribe in Python; observe disconnect behavior.
- [ ] Consume Redis Streams with a consumer group and explicit acknowledgments.
- [ ] Compare Streams semantics with Kafka in `kafka-basics`.

**Environment (Python):** See [`uv-setup.md`](../uv-setup.md).
