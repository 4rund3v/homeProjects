# Basics: consensus

[Back](README.md)

## Why

Learn consensus by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: Raft leader with 3 nodes

```text
nodes: L, F1, F2
log:   L=[1,2,3,4,5], F1=[1,2,3], F2=[1,2,3,4,5]
majority: 2 of 3
```

L appends entry 6 to its log. F1 and F2 ack it. Entry 6 is now committed (2 of 3 have it). If F1 dies, entry 6 is still durable via L+F2.

Now the partition: L and F1 are isolated from F2. F2 has 1 of 3 — no majority — so it cannot commit new entries. Meanwhile L+F1 form a quorum and keep accepting writes. On heal, F2's log is shorter than the committed log; it is fast-forwarded.

If instead F2 and L form the quorum and F1 is isolated, F1's log lags. It is caught up on rejoin.

Commit latency = time for entry to reach a majority. With 3 nodes and RTT = 10 ms, commit ≈ 10 ms (one RTT to one follower) rather than 20 ms (to both). The write latency is the *minimum* RTT to any majority member, not the average.

Scaled: 5-node cluster. Commit requires 3 of 5. If 2 nodes are down, 3 remain = still a majority. The p99 commit RTT is the 3rd-closest node's RTT. A 10 ms node and two 100 ms nodes: commit is ~10 ms if the leader is among the fast nodes.
