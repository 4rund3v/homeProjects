# Shared reference

These ideas recur across every domain. Use them to turn a component description into an operable system.

## Latency budgets

A request budget is consumed by queueing, serialization, network hops, storage, computation, and retries. Budget from the user-visible SLO backward; do not add independent p99 values as if they were p99 of the sum. Fan-out increases tail risk: if one request needs `n` independent calls, the probability all finish under `t` is approximately `P(single < t)^n`.

## Capacity and saturation

Measure throughput against latency. As utilization approaches saturation, queues grow and tail latency rises nonlinearly. Capacity plans need headroom for failure, deployments, skew, and bursts, not only average traffic.

## Back-pressure

Bound queues and concurrency. A full queue must produce an explicit policy: reject, shed, slow producers, spill to durable storage, or degrade quality. Unbounded buffering converts overload into an outage.

## Idempotency and retries

Retries are new attempts, not continuations. Use an idempotency key tied to the business operation, persist the result or deduplication record, and distinguish retryable timeout from definitive validation failure. Exponential backoff with jitter prevents synchronized retry storms.

## Observability

Instrument the invariant, not only infrastructure. Track request rate, errors, duration distributions, queue age, saturation, consistency lag, retry count, and recovery progress. Correlate traces across asynchronous boundaries with a durable operation ID.

## Failure injection

Test delay, dropped messages, duplicate delivery, reordered events, partial writes, leader loss, exhausted capacity, and stale reads. A timeout at one layer must not silently create a duplicate business action at another.

## Reference checklist

- Workload: rate, size, burst, fan-out, skew.
- SLO: availability, p50/p95/p99 latency, freshness, durability.
- Invariant: what must never happen?
- Source of truth: which state wins after conflict?
- Recovery: how detect, repair, and verify?
- Cost: compute, storage, egress, operational complexity.
