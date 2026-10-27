# Information: bm25

[Back](README.md)

## Why

Production systems use bm25 when a naive design fails under scale, concurrency, uneven load, or partial failure.

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

**Real numbers: 2 docs, k1=1.2, b=0.75, idf=0.18.**
- doc A (5 occurrences, len=5): score = 0.30
- doc B (1 occurrence, len=2): score = 0.22
- b=0: A=0.32, B=0.18
- b=0.5: A=0.30, B=0.25

Tuning: k1=0.5 (web), k1=2.0 (log search), b=0.75 (default)

```text
k1=1.2,b=0.75: A=0.30, B=0.22
k1=2.0,b=0.5:  A=0.33, B=0.25
```

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
