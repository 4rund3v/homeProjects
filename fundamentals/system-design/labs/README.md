# Labs

Run experiments locally. Record workload, command, result, and explanation.

## Lab sequence

1. Create a shared counter with multiple workers. Compare an unsafe increment, a mutex, and an atomic operation.
2. Run a transaction workload at different isolation levels. Observe anomalies and lock waits.
3. Add retries and duplicate delivery. Verify idempotency rather than assuming exactly-once execution.
4. Measure a spatial index with clustered and random points. Plot candidate count versus query radius.
5. Build a tiny inverted index. Measure index size, lookup latency, and ranking changes.
6. Chunk a large file, corrupt one chunk, and verify selective retry and final hash validation.
7. Compare exact cardinality with HyperLogLog across memory budgets.

For every lab, include a control run, one changed variable, expected behavior, and a failure explanation. See the [shared reference](../reference/README.md).

## Worked numbers

**Lab 1: shared counter, 8 threads × 100K increments.**
```text
unsafe:  final < 200,000 (lost updates)
atomic:  final = 200,000, ~1 ms total
mutex:   final = 200,000, ~80 ms total
```

**Lab 2: 1,000 concurrent reservations, 100 tickets.**
```text
Read Committed:  1,000 successes (oversell by 900), p99 = 2 ms
Serializable:     100 successes, 900 aborts, p99 = 15 ms
```

**Lab 3: 10% timeout rate, 10K rps.**
```text
retries = 1,000/second
dedup store = 1,000 × 64 bytes/min = 6.4 MB
duplicates without key = 1,000/second
duplicates with key    = 0
```

**Lab 4: 1M points, 3 km radius query.**
```text
geohash p6: ~3,400 candidates, p95 = 50 µs
H3 res 8:   ~4,200 candidates, p95 = 60 µs
S2 lvl 15:  ~3,100 candidates, p95 = 40 µs
```

**Lab 5: 10K documents, inverted index.**
```text
index size:   ~500 KB (20K unique terms × 25 postings × 8 bytes)
lookup p50:   ~2 ms
lookup p95:   ~8 ms (common term)
```

**Lab 6: 10 GB file, 512 MB chunks.**
```text
20 chunks × 41 s = 820 s total
corrupt chunk 14 → retry 6 chunks = 246 s
final hash mismatch → reject commit
```

**Lab 7: 10M unique IDs, HLL vs exact set.**
```text
exact set:  10M × 8 bytes = 80 MB, 0% error
HLL m=4096: 3 KB, ±1.6% error → ±160K on 10M
HLL m=131K: 12 KB, ±0.81% error → ±81K on 10M
```
