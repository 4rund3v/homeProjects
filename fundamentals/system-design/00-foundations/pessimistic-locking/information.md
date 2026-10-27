# Information: pessimistic locking

[Back](README.md)

## Why

Production systems use pessimistic locking when a naive design fails under scale, concurrency, uneven load, or partial failure.

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

**Real numbers: 1,000 concurrent, 1 row, 2 ms lock.**
- Ceiling: 1/2 ms = 500 rps
- 1,000 requests → p50 = 0.5 s, p99 = 1 s
- Payment call inside lock: hold = 102 ms → ceiling = 9.8 rps → 1,000 reqs = 102 s
- Payment outside: hold = 2 ms → ceiling = 500 rps → 1,000 reqs = 2 s

```text
lock in:  102 s
lock out: 2 s
```

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
