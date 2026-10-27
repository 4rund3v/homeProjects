# Information: consensus

[Back](README.md)

## Why

Production systems use consensus when a naive design fails under scale, concurrency, uneven load, or partial failure.

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

**Real numbers: 5-node Raft, RTT 5-12 ms, majority 3/5.**
- Commit RTT = 2nd-closest = 10 ms
- Partition F3+F4: L+F1+F2 = 3/5 → can commit
- 30 s partition: 30,000 log entries lag
- Catch-up: 30,000 / 10,000 entries/s = 3 s

```text
commit: 10 ms
partition: 3 s catch-up
```

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
