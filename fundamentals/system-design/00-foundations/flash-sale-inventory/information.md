# Information: flash sale inventory

[Back](README.md)

## Why

Production systems use flash sale inventory when a naive design fails under scale, concurrency, uneven load, or partial failure.

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

**Real numbers: 10K requests, 1,000 units, 10% retries.**
- DB ceiling: 5,000 conditional updates/s
- 10K in 2 s = 5,000 rps → at ceiling
- 10% retries → 11K effective → 20% over → 2,000 timeouts
- Timeouts retry → 13K → 40% over → oscillation

Token buckets (10 × 100 units):
- Per-bucket ceiling: 500 rps
- 1,000 requests/bucket drain in 2 s
- Total drain: 2 s wall-clock

```text
raw: 10K → 11K → 13K (oscillating)
buckets: 10K → 2 s drain, 0 oversell
```

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
