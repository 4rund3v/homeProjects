# Basics: cap pacelc

[Back](README.md)

## Why

Learn cap pacelc by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: three regions, one partition

```text
N = 3 replicas (us-east, us-west, eu-west)
W = 2, R = 2, so W + R > N  → strong reads
inter-region RTT: east↔west 70 ms, east↔eu 90 ms, west↔eu 140 ms
```

A write must reach 2 of 3 replicas. A client in us-east writing to the us-east leader replicates to the nearest follower: write latency ≈ 70 ms + local commit ≈ 75 ms.

A partition cuts east↔west and east↔eu:

```text
before:  east | west | eu   all connected
during:  east | west+eu     east isolated
```

- **CP choice:** east (no quorum of 2 reachable) rejects writes. Availability loss = the east region's entire write traffic.
- **AP choice:** east keeps serving writes with local data; west+eu also serve writes. On heal, conflicting versions must merge. If east took 300 writes and west took 250 during a 60-second partition, up to 550 writes need reconciliation.

### The EL in PACELC (no partition)

Same cluster, healthy network. To make writes fast, the team switches to `W = 1`:

```text
W=1: write latency ≈ 5 ms (local only)
R=2: read must still contact 2 replicas → 70–140 ms
```

They traded consistency for latency: `W + R = 3 = N`, so reads remain strong only if the W=1 replica is always in the read set — which it is not guaranteed to be. A read can miss the just-written value. That is the everyday, no-partition trade: **else latency**.

### Numbers to remember

| Config | Write | Read | Strong? |
|---|---|---|---|
| W=2, R=2, N=3 | ~75 ms | ~75 ms | yes |
| W=1, R=1, N=3 | ~5 ms | ~5 ms | no |
| W=2, R=1, N=3 | ~75 ms | ~5 ms | yes (if read hits updated replica) |

Scaled: 10 regions with W=2. A write from the farthest region waits on the 2nd closest replica; p99 write latency approaches the 2nd-worst RTT in the set.
