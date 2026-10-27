# Information: failure handling

[Back](README.md)

## Why

Production systems use failure handling when a naive design fails under scale, concurrency, uneven load, or partial failure.

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

**Real numbers: 20% dependency failure, 1,000 rps, 5 s timeout.**
- No breaker: 1,000 × 5 s = 5,000 s/s blocked
- Breaker open: 1,000 × 1 ms = 1 s/s blocked
- Probe: 1/5 s, half-open: 100 rps
- Dependency sustains 50 rps → 2 cycles to settle

```text
no breaker: 5,000 s/s
breaker:    1 s/s
```

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
