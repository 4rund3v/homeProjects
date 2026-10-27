# Failure handling patterns

[Back](../../README.md)

## Why

Distributed systems fail. Retries duplicate; timeouts create ambiguity; partitions force trade-offs. A failure-handling design is a set of decisions about what each failure mode is safe to automate.

## How

### Timeouts and retries

Time out the request. On timeout, the operation may have succeeded on the server. A safe retry must be idempotent or carry a key the server recognizes.

Backoff with jitter:

```text
delay = base * 2^n + random()
```

Cap the delay. Use a circuit breaker: if a dependency has failed enough times, stop calling it for a window and return a fast, honest failure.

### Bulkheads

Isolate pools by dependency. A slow database pool must not drain a fast read pool. Bulkheads are bounded queues plus resource limits.

### Fallbacks and degradation

Return a stale or partial answer when the source of truth is unavailable. A fallback must be labeled so the caller knows it is degraded. A fallback that quietly returns wrong data is worse than an error.

### Durable state

- **Write-ahead log** for ordered state.
- **Outbox** for event delivery with a transactional write.
- **Idempotency store** for request deduplication.

### Reconciliation

Periodically check the invariants. When drift appears, repair from the source of truth. Reconciliation is a backstop, not a substitute for a primary protocol.

## Under the hood

The key idea is **asynchrony with a source of truth**. Each component has a locally safe state and a protocol to converge. A component's progress is bounded by its slowest dependency; design around that.

A distributed system's state machine is not atomic; it has intermediate states and explicit recovery paths. Every intermediate state must be detectable and repairable.

## Production use cases

- Payment processor with retries and compensations.
- Search index that falls back to a smaller index while the big one rebuilds.
- Media pipeline that tolerates worker loss by checkpointing progress.
- Cache that reads through to the database with a bounded miss window.

## Trade-offs

| Pattern | Benefit | Cost |
|---|---|---|
| Retry + backoff + jitter | self-heals transient failures | amplifies load if misused |
| Circuit breaker | fast failure when dependency is down | flaps when the dependency recovers slowly |
| Idempotent consumer | safe replay | requires a key and dedup store |
| Bulkhead | isolation | more resource pools to manage |
| Reconciliation | eventual correct state | drift window |

## Observability

Dependency failure rate, circuit state, retry budget used, outbox lag, idempotency hits, and reconciliation drift.

## Lab

Add fault injection: 10% timeouts, 5% duplicates, 2% order reordering. A payment flow must never charge twice.

## Worked examples

**Situation: dependency degrades to 20% availability, 5 s p99.**
```text
1,000 rps to dependency
failure rate = 20%
without breaker: 1,000 × 5 s timeout = 5,000 s of blocked time per second
with breaker (open after 20 failures in 100):
  1,000 rps fail in ~1 ms → 1 s of blocked time
  probe: 1 request / 5 s
  half-open: 10% × 1,000 = 100 rps admitted
```
Dependency can sustain 50 rps. Half-open admission 100 rps > 50 rps → 2 cycles to settle. Total user-facing degradation = 2 × 5 s = 10 s, vs 30 s (MTTR) without the breaker.

Scaled: 10 dependencies, each with a breaker. The total blocked time without breakers: 10 × 1,000 × 5 s = 50,000 s/second. The thread pool is exhausted in the first 0.5 s. With breakers: 10 × 1 ms = 10 ms/second. The breakers are the difference between a partial degradation and a full outage.

```text
t=0:    dependency degrades
t=1:    100 requests, 20 fail → breaker opens
t=1-6:  fast fail, 1 probe / 5 s
t=6:    probe succeeds → half-open
t=6.5:  10% admitted, 50 rps sustained → close
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
