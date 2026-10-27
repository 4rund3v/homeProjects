# Information: hyperloglog

[Back](README.md)

## Why

Production systems use hyperloglog when a naive design fails under scale, concurrency, uneven load, or partial failure.

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

**Real numbers: 10M daily uniques, ±1% target.**
- 4,096 regs: 3 KB, 1.6% error → ±320K
- 131,072 regs: 12 KB, 0.81% error → ±81K
- Merge: 100 shards × 3 KB = 300 KB vs 80 MB raw

```text
4,096: 3 KB, ±320K
131,072: 12 KB, ±81K
```

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
