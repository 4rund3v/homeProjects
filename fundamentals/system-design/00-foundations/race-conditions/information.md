# Information: race conditions

[Back](README.md)

## Why

Production systems use race conditions when a naive design fails under scale, concurrency, uneven load, or partial failure.

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

**Real numbers: 2 workers, 10K jobs, 100 rps each.**
- No guard: 10 ms overlap × 200 rps = 200 duplicates/second
- CAS guard: 0 duplicates, +0.5 ms per claim (index lookup)
- Cost of correctness: 200 × 0.5 ms = 0.1 s/s of extra work — negligible vs the cost of 200 duplicate payments

At 10,000 jobs: 10,000 × 0.5 ms = 5 s of guard time total. One-off.

```text
no guard:  200 duplicates/s
CAS:       0 duplicates, +5 s total
```

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
