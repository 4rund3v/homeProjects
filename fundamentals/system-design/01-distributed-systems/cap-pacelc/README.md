# CAP and PACELC

[Back](../../README.md)

## Why

When a network partition occurs, a service must choose whether it continues accepting requests or refuses them. The choice has consequences for correctness and user experience.

## How

### CAP

Three properties, and a system can fully satisfy at most two during a partition:

- **C**onsistency — all nodes agree on one value.
- **A**vailability — every request receives a response.
- **P**artition tolerance — the system operates despite message loss between nodes.

Partition tolerance is not optional in a distributed system: networks fail. So the real choice is **CP** (favor correctness, refuse or block during partition) or **AP** (favor progress, answer with possibly stale or local data).

```text
      consistent and available
        \
         \
          [no partition]
         / \
        /   \
    [CP]     [AP]
```

A CP store may stop accepting writes to a minority of replicas during a partition. An AP store continues accepting writes and reconciles later.

### PACELC

CAP is silent when there is no partition. PACELC makes the normal-case trade explicit:

- **P**artition **A**vailability else **C**onsistency
- **E**lse (no partition) **L**atency else **C**onsistency

This second clause matters: in a healthy network you can still trade off. A multi-region store may write to the primary region and read from the nearest, accepting a latency bound rather than strong consistency.

## Under the hood

The mechanics that implement CAP/PACELC:

- **Quorum rules** — write to `W`, read from `R`, require `W + R > N` for strong reads.
- **Conflict resolution** — last-write-wins, version vectors, or application merge.
- **Leader election** — a consensus protocol chooses one source of truth.
- **Consistency levels** — strong, causal, or eventual, each with a different read path.

## Production use cases

- Money balances: CP.
- Shopping cart: AP is acceptable if the server reconciles with the account at checkout.
- Read-your-writes: causal consistency with session tokens.
- Multi-region config: CP to prevent conflicting deployments.

## Trade-offs

| Model | Strength | Weakness |
|---|---|---|
| CP | no conflicts | unavailable minority |
| AP | service continues | conflicts and reconciliation work |
| Causal | preserves ordering | weaker than linearizable |
| Eventual | fast, forgiving | stale read surprises |

## Lab

Run a key-value store with 3 replicas and 1 allowed partition. With `W=2, R=2`, verify strong reads. With `W=2, R=1`, observe the conflict set after the partition heals.

## Worked examples

**Situation: 3-region config store, W=2, R=2, 5-minute partition.**
```text
regions: us-east (leader), us-west, eu-west
RTT: east↔west 70 ms, east↔eu 90 ms
W=2, R=2, N=3 → W+R=4 > N=3 → strong reads
```
Write latency = commit + 1 RTT to nearest replica ≈ 5 + 70 = 75 ms.

Partition (east isolated): east has 1/3 of replicas → no quorum for W=2.
- **CP:** east rejects writes. Availability loss = 100% of east write traffic (~33% of total).
- **AP:** east accepts local writes. During 5 min, east takes 300 writes, west+eu take 250. On heal, 550 writes to reconcile. Conflict rate = 550 / total_writes_during_partition.

No-partition latency trade (W=1):
```text
W=1: write = 5 ms (local only)
R=2: read = 70-140 ms (must reach 2 of 3)
```
The team traded consistency for latency. A read can miss the just-written value. That is the "else latency" clause of PACELC made concrete: at 5 ms writes, 70% of reads are stale.

| Config | Write | Read | Strong? | Stale-read risk |
|---|---|---|---|---|
| W=2, R=2 | 75 ms | 75 ms | yes | 0 |
| W=1, R=1 | 5 ms | 5 ms | no | 100% until replication |
| W=1, R=2 | 5 ms | 70 ms | partial | read may miss 1 replica |

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
