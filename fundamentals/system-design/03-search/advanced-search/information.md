# Information: advanced search

[Back](README.md)

## Why

Production systems use advanced search when a naive design fails under scale, concurrency, uneven load, or partial failure.

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

**Real numbers: p95 SLO = 100 ms, 5,000 qps.**
- Top 100: 35 ms, 175 s/s CPU
- Top 50:  20 ms, 17.5 s/s CPU
- Feature store: 50,000 concurrent reads @ 5 ms p99 → 250 s/s → 2.5× SLO
- Top 50: 25,000 concurrent reads → 125 s/s → inside SLO

```text
top 100: 175 s/s CPU
top 50:  17.5 s/s CPU
```

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
