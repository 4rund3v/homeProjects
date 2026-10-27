# Information: concurrency fundamentals

[Back](README.md)

## Why

Production systems use concurrency fundamentals when a naive design fails under scale, concurrency, uneven load, or partial failure.

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

**Real numbers: 8 threads, 100K increments.**
- Unsafe: final < 200K (lost updates)
- Atomic: final = 200K, ~1 ms total (cache line hot, ~5 ns CAS)
- Mutex: final = 200K, ~80 ms total (800K acquires × ~100 ns)
- Cache-line ping-pong: 8 threads × 100K = 800K cache-line transfers × ~100 ns = 80 ms minimum even without lock overhead

Throughput ceiling for a global counter: ~1M increments/second before cache-line ping-pong dominates. Sharding to 8 per-thread counters + periodic merge: 8 × 1M = 8M increments/second, merge cost = 8 additions × ~100 ns = 0.8 µs every 100K increments.

```text
global counter:  ~1M/s ceiling
sharded:         ~8M/s ceiling
```

Read the domain README and the shared [reference](../../reference/README.md). Apply the [design checklist](../../design-review-checklist.md).
