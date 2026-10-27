# Information: cap pacelc

[Back](README.md)

## Why

Production systems use cap pacelc when a naive design fails under scale, concurrency, uneven load, or partial failure.

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

**Real numbers: 3 regions, W=2, R=2, 5-min partition.**
- Write latency: 5 + 70 = 75 ms
- Partition: east isolated, 1/3 quorum → CP rejects, AP accepts
- 5 min: east 300 writes, west+eu 250 → 550 to reconcile

No partition (W=1): write = 5 ms, read = 70-140 ms
| Config | Write | Read | Stale risk |
| W=2,R=2 | 75 ms | 75 ms | 0 |
| W=1,R=1 | 5 ms | 5 ms | 100% |
| W=1,R=2 | 5 ms | 70 ms | partial |

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
