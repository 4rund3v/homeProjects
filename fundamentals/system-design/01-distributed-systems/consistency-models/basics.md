# Basics: consistency models

[Back](README.md)

## Why

Learn consistency models by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: read-your-writes on a shopping cart

```text
user adds item to cart, writes to R1
user immediately sees "add to cart" confirmation, reads from R2
```

With **eventual consistency**, the read from R2 misses the write and shows an empty cart. With **session consistency**, the user's next read is routed to the replica that saw their last write — they always see their own cart.

Quantifying freshness: if replication lag p99 is 500 ms and the SLO is "user sees their own write within 100 ms," session consistency (local routing) is required, not just eventual. Scaled: 100,000 cart reads/second. Routing to the "own write" replica reduces cross-region read RTT from 90 ms to 5 ms.
