# Database locking and concurrency

[Back](../../README.md)

## Why

A database must coordinate readers and writers while preserving throughput. Lock scope, lock duration, and access order determine whether concurrent work scales or forms a lock convoy.

## How

A typical row update:

```text
begin → find row → acquire exclusive lock → validate → write → commit/release
```

A read under MVCC may avoid blocking a writer by reading an older committed version. A locking read intentionally waits for the current version when the next decision depends on it.

## Under the hood

Lock granularity ranges from row to page to table. Fine locks improve concurrency but consume memory and increase lock-manager work. Coarse locks reduce metadata overhead but create contention.

The lock manager maintains a wait-for graph. A cycle means deadlock. Engines usually detect the cycle and abort one transaction. Lock escalation can convert many row locks into a table lock, surprising a workload that was fast at low volume.

Index choice changes locking. A missing or unusable index can force a scan and lock far more rows or predicates than intended.

## Production use cases

- `SELECT ... FOR UPDATE` for a reservation row.
- Unique-key insert for deduplication.
- Range lock to prevent a conflicting booking in a time interval.

## Trade-offs and failure modes

| Decision | Benefit | Risk |
|---|---|---|
| Row lock | high concurrency | lock metadata and deadlocks |
| Table lock | low metadata overhead | broad blocking |
| MVCC snapshot | readers do not block writers | stale reads and version cleanup |
| Lock timeout | bounded request latency | caller must retry safely |

## Observability

Track lock waits by table/index, transaction age, deadlock victims, escalation events, and blocked query fingerprints. Alert on oldest transaction age; long snapshots can prevent version cleanup.

## Lab

Run two sessions updating rows in the same order, then opposite orders. Compare completion time and deadlock behavior. Add an index and observe the lock footprint.

## Worked examples

**Situation: UPDATE on a 10M-row table with vs without index.**
Without index: the UPDATE scans 10M rows, locks ~10M rows. Lock metadata: 10M × 16 bytes = 160 MB. With a selective index on `order_id`: 1 row locked, 16 bytes. At 1,000 concurrent transactions, the no-index case holds 160 GB of lock metadata; the indexed case holds 16 KB. The indexed version also avoids lock escalation (which would convert 10M row locks into a table lock).

```text
no index:  1,000 txns × 10M rows = 10B row locks → escalation → table lock
with idx:  1,000 txns × 1 row   = 1,000 row locks → no escalation
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
