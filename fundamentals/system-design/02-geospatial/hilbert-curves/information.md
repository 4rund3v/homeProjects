# Information: hilbert curves

[Back](README.md)

## Why

Production systems use hilbert curves when a naive design fails under scale, concurrency, uneven load, or partial failure.

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

**Real numbers: 1024×1024 grid, 10×10 window, 1M points.**
- Row-major: 10,240 cells scanned, 99% waste → 160 KB I/O
- Hilbert: 400 cells scanned, 75% waste → 6.4 KB I/O
- I/O reduction: 25×

```text
row-major: 160 KB
hilbert:   6.4 KB (25× less)
```

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
