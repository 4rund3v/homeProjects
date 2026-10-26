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
