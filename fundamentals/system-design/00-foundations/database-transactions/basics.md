# Basics: database transactions

[Back](README.md)

## Why

Learn database transactions by first naming the invariant, workload, and failure that make the topic necessary.

## How

Start with one concrete request and trace it from input to durable state. Then identify where concurrency, latency, failure, or approximation changes the result.

## Under the hood

Separate the control path from the data path. Record the state machine, key data structures, complexity, and the boundary where correctness is enforced.

## Checkpoint

- What must never happen?
- Which component owns the truth?
- What does a timeout mean?
- What measurement would falsify the design?

## Worked example: order + outbox in one commit

```text
order table:   1 row, 200 bytes
outbox table:  1 row, 400 bytes
commit rate:   500 orders/second
```

Each transaction writes 600 bytes plus WAL overhead. At 500 orders/second, that is 300 KB/s of WAL plus indexes.

The outbox publisher polls every 100 ms. If each poll takes up to 1,000 unpublished rows and delivery takes 50 ms/row:

```text
drain rate = 1,000 / (100 ms + 50 ms) ≈ 6,666 rows/second
```

If orders spike to 5,000/second, the publisher must batch; otherwise outbox lag grows unboundedly: `lag = arrival − drain`. Alert when lag exceeds the freshness SLO (for example, 5 seconds of age).

Dual-write failure without an outbox: the database commits but the publish fails. With 0.1% publish failure at 500 orders/second, roughly one order every 20 seconds loses its downstream event. The outbox moves that failure into a retryable queue.
