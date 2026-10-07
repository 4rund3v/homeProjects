# Kafka Basics

## What this project exists to solve
Learn event-streaming semantics by producing and consuming events through a small local Kafka-compatible broker. The goal is to understand partition behavior, consumer groups, delivery guarantees, and the difference between what Kafka promises and what applications must still enforce.

## Success criteria / completion metrics
- Produce from Go and consume from Python in one partition with observed ordering.
- Consumer-group assignment and rebalance demonstrated with at least two consumers.
- Idempotent processing tested under forced duplicate delivery; lag measured.
- `NOTES.md` states precisely which guarantees Kafka provides and which the application must provide; no unsupported "exactly once" claims.
- Optional feed into `telemetry-hub` log pipeline demonstrated end to end.
- Local CI gates tests and container image builds.

## Prerequisites and dependencies
- `go-fundamentals`, `python-refresh`.
- `uv` for Python (see `../uv-setup.md`).
- Compare with `redis-cache` to clarify semantics.

## Tools, libraries, and runtime
- Kafka-compatible local broker in KRaft mode (no ZooKeeper).
- Go client library.
- Python client library; `uv` for environment.
- Docker Compose for broker and optional consumers/producers.
- Local CI.

## Learning objectives (skills practiced)
- Topics, partitions, keys, and how partition assignment determines ordering.
- Consumer groups, rebalances, and offset commits.
- At-least-once delivery and why exactly-once requires application-side idempotency.
- Consumer lag and what it indicates about throughput.
- Local Kafka operation and CLI inspection.

## Architecture / design note
Minimal producer/consumer services and a small harness:

```
producer/
  main.go
consumer/
  main.py                    # uv-managed Python consumer
tests/
  integration/
    kafka_test.go
docker-compose.yaml
```

One topic with at least two partitions; one producer group and one consumer group; enough to observe assignment and ordering without building a large system.

## Test strategy
- Integration tests start a broker in Docker, produce known events, and consume them back in order within a partition.
- Duplicate delivery test: redeliver a committed offset and show the consumer processes the same event again; this proves at-least-once behavior and motivates idempotency.
- Consumer group test: add and remove consumers, observe rebalance and lag.
- CI starts the broker in Docker and runs Go and Python tests.

## Documentation checklist
- `README.md` with setup, producer/consumer examples, broker configuration, and run commands.
- `NOTES.md` with guarantees table (what Kafka guarantees vs. what the application guarantees) and a comparison with `redis-cache`.
- CLI commands to inspect topics, offsets, and consumer groups.

## API contract
No HTTP API required for Kafka itself. If an HTTP API is added to produce events, document it in OpenAPI.

## UI / status surfaces
Optional status page showing consumer lag and recent events; omitted unless it adds real debugging value.

## Security boundaries to think about
- Local Kafka broker should not be exposed beyond the local development network.
- ACLs are useful even in local experiments to practice least privilege; document them if added.
- Do not treat broker-hosted topics as durable backups without replication and retention planning.

## Profiling plan
Profile is not the focus. Throughput and lag measurement with stable input rates is acceptable; use a simple before/after table rather than detailed profiles.

## How this project fits into the curriculum
First event-streaming exposure. `telemetry-hub` may use Kafka as an optional event log later; the semantics are established here.

## Suggested milestone walkthrough
1. **Single partition produce/consume.** Produce from Go, consume from Python; verify order and content.
2. **Consumer group.** Add a second consumer; observe group assignment and rebalance.
3. **Idempotency.** Force a duplicate and make processing idempotent; document the application contract.
4. **Lag and observation.** Measure consumer lag; document what lag indicates.
5. **Container + CI.** Compose the broker and run tests in CI.
6. **Telemetry integration (optional).** Feed events into `telemetry-hub` and observe end-to-end.

## Reference notes and resources
- Apache Kafka documentation and KRaft mode notes.
- Go and Python Kafka client documentation.
- Confluent blog and docs on consumer groups and exactly-once semantics.
