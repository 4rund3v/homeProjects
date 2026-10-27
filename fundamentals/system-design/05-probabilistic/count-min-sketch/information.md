# Information: count min sketch

[Back](README.md)

## Why

Production systems use count min sketch when a naive design fails under scale, concurrency, uneven load, or partial failure.

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

**Real numbers: 10M distinct IPs, 100M events/day, ε=0.01.**
- 272 × 5 × 8 = 10.9 KB
- Exact map: 80 MB → 7,300× smaller
- Collision: heavy key (1M hits) inflates rare key by ~18,000
- 32-bit overflow: 3.6M/day at 1% → safe for 1,000 days

```text
CMS: 10.9 KB
exact: 80 MB
```

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
