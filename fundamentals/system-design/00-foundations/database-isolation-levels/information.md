# Information: database isolation levels

[Back](README.md)

## Why

Production systems use database isolation levels when a naive design fails under scale, concurrency, uneven load, or partial failure.

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

**Real numbers: 1,000 concurrent reservations, 100 tickets.**
- Read Committed: 1,000 readers see 100 → oversell by 900
- Serializable: engine aborts 900, 100 succeed
- Retry (10 ms base, 10 retries): ~5% still fail
- p99 latency: RC = 2 ms, SER = 15 ms (7.5× cost)

At 1,000 rps on one SKU: SER p99 = 15 ms → 1,000 × 15 ms = 15 s/s of lock time. The DB is busy. Sharding to 10 SKUs: 1,000 rps / 10 = 100 rps/SKU → p99 = 2 ms again.

```text
1 SKU, SER: p99 = 15 ms, 15 s/s lock time
10 SKUs, SER: p99 = 2 ms, 0.2 s/s lock time
```

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
