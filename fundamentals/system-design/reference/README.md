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

## Worked numbers

**Latency budget: p95 = 100 ms, 5 sequential hops.**
```text
hop 1 (CDN):    10 ms
hop 2 (API):     5 ms compute
hop 3 (DB):      3 ms
hop 4 (cache):   2 ms
hop 5 (metrics): 1 ms
sum = 21 ms p50 → 79 ms headroom
```
Tail risk: p99 of each hop is ~5× p50. 5 hops × 5× = 25× p50 of sum = 525 ms p99. The p99 SLO is not the sum of p99s — it is the p99 of the sum, which is dominated by the slowest hop.

**Fan-out: 1 request = 3 independent calls.**
```text
P(all 3 < 50 ms) = P(single < 50 ms)^3
if P(single < 50 ms) = 0.95 → 0.95^3 = 0.857
→ 14.3% of requests exceed 50 ms even if each call is fast
```

**Back-pressure: bounded queue of 1000, 5,000 rps arrival, 2,000 rps service.**
```text
net growth = 5,000 - 2,000 = 3,000/s
queue fills in 1,000 / 3,000 = 0.33 s
after full: 3,000 rps shed (or producers slow)
```

**Idempotency: 10K rps, 1% timeout rate.**
```text
retries = 10K × 0.01 = 100/second
dedup store: 100 × 64 bytes = 6.4 KB/second
1-minute window: 100 × 60 × 64 = 384 KB
```

**Failure injection: 5% duplicate delivery, 1,000 rps.**
```text
duplicates = 50/second
without idempotency: 50 duplicate business ops/second
with idempotency: 50 no-ops, 0 duplicates
```
