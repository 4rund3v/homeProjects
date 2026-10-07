# Redis Cache and Streams

## What this project exists to solve
Learn Redis as a cache and as a lightweight message backbone, and understand when each use case is appropriate, what failure modes look like, and how correctness and performance trade off.

## Success criteria / completion metrics
- Cache-aside integration for a small API; documented hit ratio and latency.
- Pub/sub demo in Go publishing and Python subscribing, with observed ordering under a disconnect/reconnect scenario.
- Redis Streams consumer-group example with explicit acknowledgment and consumer-group rebalance observation.
- A `NOTES.md` comparing Redis pub/sub and Streams semantics with Kafka semantics; clear on what each guarantees and what it does not.
- Local CI gates tests and container build.

## Prerequisites and dependencies
- `go-fundamentals`, `python-refresh`; `drf-basics` for a realistic endpoint to cache.
- `uv` for Python (see `../uv-setup.md`).

## Tools, libraries, and runtime
- Redis in Docker.
- Go `go-redis`; Python `redis-py`.
- Optional metrics: Redis `INFO`, simple counters.
- Docker; local CI.

## Learning objectives (skills practiced)
- Cache-aside vs. write-through vs. write-behind semantics.
- TTL and invalidation: when cached data is stale and how the system recovers.
- Pub/sub: at-most-once delivery, subscription behavior on disconnect, channel naming.
- Redis Streams consumer groups: offset semantics, acknowledgments, pending entries, and group rebalances.
- Backpressure and consumer lag: when producers outrun consumers.
- Cache stampedes and thundering-herd mitigations at a conceptual level.

## Architecture / design note
Isolate cache and stream logic behind small interfaces so experiments are interchangeable:

```
cmd/cache/main.go               # optional demo server
internal/
  cache.go                      # cache-aside interface
  pubsub.go                     # pub/sub publisher and subscriber
  stream.go                     # Streams consumer group
python/
  subscriber.py                 # Python pub/sub + stream consumer
```

Each concern has one public interface and one test double.

## Test strategy
- Unit tests with an in-memory or containerized Redis instance in CI.
- Cache tests: hit, miss, TTL expiry, invalidation, and cache-down behavior.
- Pub/sub tests: message ordering, disconnect behavior, multiple subscribers.
- Streams tests: group membership, pending entries, acknowledgment, and rebalance behavior under failure.
- CI uses a Redis container; tests run against a known dataset.

## Documentation checklist
- `README.md` with setup, scenarios, `redis-py` and `go-redis` examples, and local run instructions.
- `NOTES.md` with Redis vs. Kafka semantics comparison and a decision guide: when Redis is appropriate and when Kafka is better.
- Contract notes for each scenario: delivery guarantees, ordering, retention.

## API contract
Optional API endpoints for the cache demo; document in OpenAPI if present.

## UI / status surfaces
Optional simple status page showing cache hit ratio and recent pub/sub or stream events. Do not build a large UI.

## Security boundaries to think about
- Redis should not be exposed to external networks in local experiments; bind locally or run in Docker without port publishing to the host.
- Cached responses must not include secrets unless the cache itself is protected.
- Stream and pub/sub channel naming should be validated to avoid unintended data mixing.
- Acknowledge Redis ACLs even in local use to practice least privilege.

## Profiling plan
Profile only if latency or throughput becomes a meaningful question. Define a workload (requests per second, cache hit ratio), capture baseline, and compare one change at a time.

## How this project fits into the curriculum
Provides caching patterns for `drf-basics` and an event-consumption pattern for `kafka-basics` comparison. Local CI and Docker habits carry into `k3s-helm`.

## Suggested milestone walkthrough
1. **Cache-aside.** Integrate Redis caching with one API endpoint; measure hit ratio.
2. **TTL and invalidation.** Add expiry and manual invalidation; document stale-data behavior.
3. **Pub/sub.** Go publisher and Python subscriber; observe ordering and reconnect behavior.
4. **Streams.** Consumer group with acknowledgments; compare with Kafka in `kafka-basics`.
5. **Container + CI.** Redis in Compose; CI runs Redis-backed tests and image build.

## Reference notes and resources
- Redis documentation: cache, pub/sub, Streams.
- `go-redis` and `redis-py` docs.
- Redis Streams consumer-group semantics and `XREADGROUP` behavior.
