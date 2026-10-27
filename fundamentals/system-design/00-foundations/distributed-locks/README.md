# Distributed locks

[Back](../../README.md)

## Why

A process-local mutex cannot coordinate workers on different machines. A distributed lock is useful when exactly one owner should perform a lease-bounded action, such as leader-only cleanup or one scheduled job per key.

It is not a substitute for a database constraint. If correctness depends on exclusive ownership, the protected resource needs a **fencing token** or conditional write so an old owner cannot continue after its lease expires.

## How

```text
Worker A ── acquire(key, ttl) ──> Lock service: token 41
Worker B ── acquire(key, ttl) ──> denied
Worker A ── write(resource, fencing=41) ──> store accepts
Worker A pauses; lease expires
Worker B ── acquire(key, ttl) ──> token 42
Worker A resumes; write(fencing=41) ──> store rejects
```

Acquisition must be atomic: create the key only if absent, attach an owner and expiry, and return a monotonically increasing fencing token.

## Under the hood

A lease is time-bounded ownership. Expiration is based on the lock service's clock, not a worker's local clock. A worker must renew before the lease deadline, but a pause, network delay, or overloaded runtime can make renewal fail.

The critical design is the fencing check at the resource boundary:

```sql
UPDATE resource
SET value = ?, last_fence = ?
WHERE id = ? AND last_fence < ?;
```

Without fencing, a stale worker can write after a new owner starts. Heartbeats alone do not solve this: a paused worker cannot observe that it lost ownership.

### Safety versus liveness

- **Safety:** never accept writes from two owners at once.
- **Liveness:** eventually allow a healthy worker to acquire after failure.

Short leases improve liveness but increase false expiration. Long leases reduce churn but delay recovery. The right value follows the longest expected pause plus network and service jitter, with margin.

## Production use cases

- One scheduler leader per shard.
- Duplicate expensive cache rebuild suppression.
- One migration runner.
- Per-customer serialization of a non-transactional external API.

Avoid using a lock to implement inventory correctness when a conditional database update is available.

## Trade-offs and failure modes

| Design | Gains | Costs | Failure |
|---|---|---|---|
| DB row lock | strong local semantics | blocks, one store boundary | long transaction |
| Lease lock | recovers after owner crash | expiry ambiguity | stale owner writes |
| Fenced lease | stale writes rejected | resource must enforce token | missing enforcement |
| Queue ownership | ordered processing | throughput and replay complexity | poison message |

## Observability

Track acquisition latency, contention, renew failures, expiry count, owner changes, fencing rejections, and critical-section duration. Alert on repeated renew failures before they become correctness incidents.

## Lab

Run two workers against a lock with a short lease. Pause worker A after acquisition, let B acquire, then have A write. First run without fencing; then add a fencing token and confirm the stale write is rejected.

## Worked examples

**Situation: 10-minute job, 5-second lease, 3-second renew.**
Releases needed: 600 s / 3 s = 200 renewals. Each renewal is 1 RTT (~10 ms). Total protocol overhead = 200 × 10 ms = 2 s out of 600 s = 0.33%. Negligible.

Stale-owner scenario: worker A pauses 4 s (GC). At t=5 s, lease expires. Worker B acquires at t=5.1 s (token 8). A resumes at t=5.5 s and sends its next write with token 7. The store rejects because `last_fence=8 > 7`. Without fencing, A's write succeeds and corrupts B's work. The fencing check is the invariant; it adds 1 integer comparison to the write path (~0 ns).

```text
t=0:   A acquires, token 7
t=3:   A renews
t=5:   A pauses, lease expires
t=5.1: B acquires, token 8
t=5.5: A resumes, write(token 7) → rejected
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
