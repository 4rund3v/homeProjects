# Information: introduction

[Back](README.md)

## Why

Production systems use introduction when a naive design fails under scale, concurrency, uneven load, or partial failure.

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

**Real numbers: 3-hop payment, 10K rps, 1% network failures.**
- p50 = 18 ms, p90 = 58 ms, p99 = 218 ms
- Duplicates without idempotency: 100/second
- Dedup store: 100K keys/min × 64 bytes = 6.4 MB (1-min TTL)

```text
duplicates: 100/s
dedup: 6.4 MB
```

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
