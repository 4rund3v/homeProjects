# Information: elasticsearch

[Back](README.md)

## Why

Production systems use elasticsearch when a naive design fails under scale, concurrency, uneven load, or partial failure.

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

**Real numbers: 100 GB index, 5 shards, 30 GB heap/node.**
- Cold fraction: 4/60 GB = 6.7% → p99 = 500 ms
- Refresh 1s: 86,400 segments/day → 15% merge CPU
- Refresh 30s: 2,880 segments/day → 0.5% merge CPU
- Bulk 5,000 × 150 MB @ 100 rps = 15 GB/s → 5× over disk ceiling

```text
cold: 6.7% → p99 = 500 ms
bulk 100 rps: 15 GB/s (5× over)
```

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
