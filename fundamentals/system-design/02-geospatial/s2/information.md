# Information: s2

[Back](README.md)

## Why

Production systems use s2 when a naive design fails under scale, concurrency, uneven load, or partial failure.

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

**Real numbers: 1M vehicles, S2 level 16, 5×5 km district.**
- ~25 cells
- 25 × 40 vehicles = 1,000 candidates
- Full scan: 1M × 10 ns = 10 ms
- S2: 25 × 10 ns + 1,000 × 100 ns = 100 µs
- 100× faster

```text
full: 10 ms
S2:   100 µs
```

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
