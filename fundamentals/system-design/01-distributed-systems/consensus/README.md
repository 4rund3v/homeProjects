# Consensus algorithms

[Back](../../README.md)

## Why

Some state must have exactly one current value everywhere at once: which node is the leader, which write is the `N`-th, which config version is active. Consensus is how a set of possibly-failing nodes agree on one value.

## How

Consensus solves two related problems:

- **Agreement** — all correct nodes propose values and end up on the same one.
- **Termination** — a value is eventually decided.
- **Validity** — the decided value was proposed by some correct node.

A consensus algorithm is the mechanism that orders and commits values across a set of replicas.

## Under the hood

The central difficulty is that nodes fail asynchronously. A correct consensus protocol is a two-part design:

1. **A total order on proposals.** Nodes number their proposals with a monotonic sequence.
2. **A commit rule.** A value is decided only after enough nodes have seen it.

Two dominant families:

### Paxos-style (classic)

A proposal has a number. A proposer is accepted by a **majority**. A new proposer must first find out the highest-numbered proposal any majority already accepted; it then proposes a value at least that high. This prevents an old, forgotten value from being re-decided.

Safety comes from the quorum intersection property: any two majorities of a set of size `N` overlap, so no two different values can both be committed.

### Raft (the modern default)

Raft makes consensus easier to reason about by decomposing it into:

- **Leader election** — a node that receives enough votes becomes leader.
- **Log replication** — the leader appends entries and commits them when a majority has them.
- **Safety rules** — a candidate cannot win unless its log is at least as up-to-date as the majority's; a leader never overwrites an uncommitted entry in a follower's log.

Raft's key invariant: a committed entry is replicated on a majority; since majorities intersect, no later leader can lack it. That is why commit means "on a majority," not "on every node."

```text
term 3:  [F1][L2][F3]
          F1: no entries
          L2: committed up to 7
          F3: has up to 7
          → L2 wins, majority of up-to-date logs
```

### Why exactly N or N+1

Use an odd number of replicas so that a minority can be down without quorum being lost. For 3 replicas, any 2 still form a majority. For 4, you need 3, so losing one node still works but losing two does not.

## Consensus versus agreement on replicas

Consensus orders *who writes* and *in what order*. Multi-replica data stores add a second layer: how reads are served and how strongly they are consistent. A store may use Raft to order writes and then use quorum reads (`R + W > N`) to serve strongly consistent reads from any replica.

## Production use cases

- Replicated state machine (etcd, Consul, ZooKeeper).
- Distributed configuration store.
- Leader election for a primary-replica database.
- Ordering events before fan-out.

## Trade-offs and failure modes

| Choice | Gains | Costs | Failure |
|---|---|---|---|
| 3 replicas | quorum with one down | 2× write cost | third down → still fine |
| 5 replicas | two down tolerated | more write cost | more vote traffic |
| Single leader | simple commit | leader is hot spot | split brain if quorum lost |
| Consensus log | total order | commit latency = slowest majority | leader lag |

The classic danger is **split brain**: if the network partitions into two groups and both think they have a majority, two leaders can issue conflicting writes. Quorum rules prevent this only if the partition respects a fixed node set. A node that re-joins with a *new* partitioning may break the assumption; the protocol must handle membership changes with joint consensus.

## Observability

Current term, leader ID, committed index, per-replica log index, vote traffic, and the gap between the leader's log and the majority's. A large gap means commit latency will rise.

## Lab

Run a 3-node Raft. Kill the leader; confirm election in the remaining two. Kill a second node; confirm the system stops accepting writes (no quorum). Restore and confirm the committed log survives.

## Worked examples

**Situation: 5-node Raft, commit latency under partition.**
```text
nodes: L, F1, F2, F3, F4
RTT: L↔F1 5 ms, L↔F2 10 ms, L↔F3 8 ms, L↔F4 12 ms
majority = 3 of 5
```
Commit = L + 2 of F1,F2,F3,F4. L's commit time = 2nd-closest RTT = 10 ms (F2).

Partition: F3+F4 isolated from L+F1+F2.
- L+F1+F2 = 3 of 5 → quorum → can commit
- F3+F4 = 2 of 5 → no quorum → cannot commit
- After 30 s, F3+F4 see L's heartbeat loss → F3 starts election → fails (no quorum)
- L continues accepting writes; F3+F4's log falls behind

On heal: F3+F4 catch up to L's committed log. The 30-second partition caused 30 s × 1,000 writes/s = 30,000 log entries of lag. At 10,000 entries/s catch-up speed: 3 s to converge.

Scaled: 7-node cluster, majority = 4. Same partition math. The commit RTT is the 4th-closest RTT. If the 4th-closest is 50 ms, commit = 50 ms. Adding nodes adds RTT cost to the commit path.

```text
L ──5ms── F1
L ──10ms── F2
L ──8ms─── F3
L ──12ms── F4
commit = L + F1 + F2 = 10 ms (2nd RTT)
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
