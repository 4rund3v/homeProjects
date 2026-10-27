# Information: database locking

[Back](README.md)

## Why

Production systems use database locking when a naive design fails under scale, concurrency, uneven load, or partial failure.

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

**Real numbers: 10M-row table, 1,000 concurrent transactions.**
- No index: 10M × 1,000 = 10B row locks → lock escalation → table lock
- With index: 1,000 × 1 = 1,000 row locks
- Lock metadata: 10B × 16 bytes = 160 TB → OOM
- With index: 1,000 × 16 bytes = 16 KB

The missing index is a 10,000× cost multiplier on lock footprint.

```text
no index: 10B locks, 160 TB metadata
with idx: 1,000 locks, 16 KB
```

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
