# Information: mutexes semaphores deadlocks

[Back](README.md)

## Why

Production systems use mutexes semaphores deadlocks when a naive design fails under scale, concurrency, uneven load, or partial failure.

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

**Real numbers: DB pool of 50, 200 goroutines, 20 ms hold.**
- Throughput: 50/20 ms = 2,500/s
- Little's law: queue 200 → wait = 200/2,500 = 80 ms
- p99 = 20 + 80 = 100 ms
- SLO p99 < 50 ms → pool undersized
- 100 permits: wait = 100/5,000 = 20 ms → p99 = 40 ms ✓

Deadlock: 2 locks, 2 txns → kill 1 at 30 s → 1 aborted txn per 30 s window

```text
50 permits: p99 = 100 ms
100 permits: p99 = 40 ms
```

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
