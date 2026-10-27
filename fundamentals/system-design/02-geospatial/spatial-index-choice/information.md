# Information: spatial index choice

[Back](README.md)

## Why

Production systems use spatial index choice when a naive design fails under scale, concurrency, uneven load, or partial failure.

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

**Real numbers: 1M points, 3 km radius, 100 pts/km².**
- Geohash p6: 3,396 candidates, 170 ms/s CPU at 5K qps
- H3 res 8: 4,245 candidates, 210 ms/s CPU
- S2 level 15: 3,113 candidates, 155 ms/s CPU

S2 saves 15 ms/s CPU but costs 40% more index storage. At 5K qps the CPU savings are small; storage dominates.

```text
geohash: 170 ms/s CPU, smallest index
S2:      155 ms/s CPU, +40% index
```

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
