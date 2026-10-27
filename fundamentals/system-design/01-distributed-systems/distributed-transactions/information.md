# Information: distributed transactions

[Back](README.md)

## Why

Production systems use distributed transactions when a naive design fails under scale, concurrency, uneven load, or partial failure.

## How

Use the topic README as the worked mechanism. Reduce the design to inputs, state transitions, outputs, and explicit error semantics. Make retries and duplicate delivery safe before optimizing throughput.

## Under the hood

Document memory layout, index or queue behavior, persistence boundary, ordering, visibility, and recovery. State time and space complexity. Distinguish a guarantee from an implementation convention.

## Production review

| Dimension | Questions |
|---|---|
| Correctness | What invariant is enforced at the write boundary? |
| Scale | What becomes hot first? |
| Latency | What drives tail latency? |
| Failure | What happens after timeout, retry, or restart? |
| Operations | Which metric proves health? |
| Security | Can input exhaust resources or expose data? |

## Related

## Worked numbers

**Real numbers: 1,000 rps saga, 0.1% step failure.**
- Outbox growth: 3,000 rows/s
- Drain (100 ms poll, 50 ms delivery): 2,000 rows/s → 1,000 lag/s
- 60 s: 60,000 rows lag
- Fix: 500-row batch → 3,333 rows/s → no lag

2PC in-doubt: 3 concurrent in-doubt rows (at any time) vs 60K outbox rows
```text
saga outbox: 60K rows lag
2PC in-doubt: 3 rows at any time
```

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
