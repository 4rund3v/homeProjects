# Information: consistency models

[Back](README.md)

## Why

Production systems use consistency models when a naive design fails under scale, concurrency, uneven load, or partial failure.

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

**Real numbers: 100K reads/s, 50 ms replication lag.**
- Eventual: user sees empty cart for 50 ms → re-adds → duplicate
- Session: read routed to home region → 5 ms → no stale

At 1M reads/s, 50% cross-region:
- Cross-region: 500K × 65 ms extra = 32.5 s/s
- Session routing: 1M × 5 ms = 5 s/s
- 7× less latency cost

```text
cross-region: 32.5 s/s
session:      5 s/s
```

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
