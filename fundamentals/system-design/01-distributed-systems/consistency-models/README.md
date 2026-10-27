# Consistency models

[Back](../../README.md)

## Why

"Consistent" is overloaded. A design must name the exact guarantee: which writes are visible to which readers, in what order, and how fast.

## How

```text
linearizable
   │
   ├── sequential (one operation at a time)
   │
   └── eventual (converges after writes stop)
         │
         ├── causal (happens-before ordering)
         └── session (reads see the user's own writes)
```

- **Linearizability** — each operation appears to take effect at one instant between its invocation and response.
- **Sequential consistency** — operations appear in some total order consistent with the program order of each process.
- **Causal consistency** — if write A caused write B, all readers see A before B.
- **Session guarantees** — a user's own writes are visible in their own session.
- **Eventual consistency** — replicas converge after enough time.

## Under the hood

Each model changes the read path and the metadata:

- **Linearizable** reads consult the leader or verify version before returning.
- **Causal** requires a happens-before graph and clocks or sequence numbers.
- **Eventual** uses vector clocks or write timestamps plus a convergence policy.

The choice between causal and linearizable is not subtle: causal is enough for social feeds and shopping carts; linearizable is required for money, leases, and leader-only actions.

## Production use cases

- Money: linearizable.
- Feed: causal or eventual.
- Leader-only action: linearizable on the leader state.
- Cache warm-up: eventual is acceptable.

## Trade-offs

| Model | Cost | Strength |
|---|---|---|
| Linearizable | leader round-trip | strongest |
| Sequential | ordering overhead | strong but not real-time |
| Causal | dependency tracking | respects causality |
| Eventual | reconciliation | forgiving |

## Lab

Run a multi-replica store. Send a write on R1 and read R2 immediately. Under eventual consistency the read may miss the write. Under linearizable the read waits for the leader.

## Worked examples

**Situation: shopping cart, 100,000 reads/second, 50 ms replication lag.**
```text
user writes to R1 (us-east)
user reads from R2 (us-west), RTT = 70 ms
replication lag p99 = 50 ms
```
Eventual consistency: user reads empty cart for up to 50 ms after write → user sees empty cart → re-adds item → duplicate. With session consistency, the read is routed to R1 → 5 ms → user always sees their own write. Cost: cross-region reads from us-west to us-east are 70 ms instead of 5 ms. At 100,000 reads/second with 50% routed cross-region, that's 50,000 × 65 ms extra = 3.25M ms/s = 3,250 s/s of extra read time — the session-consistency routing is the cheaper option.

Scaled: 1M reads/second. Cross-region RTT 70 ms × 500K cross-region reads = 35,000 s/s of extra latency budget. Session routing to the home region: 5 ms × 1M = 5,000 s/s. 7× less latency cost.

```text
eventual:  read from R2 → miss → 50 ms stale
session:   read from R1 → hit  → 5 ms
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
