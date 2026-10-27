# Transactions

[Back](../../README.md)

## Why

A request rarely touches one field. It may debit a balance, insert an order line, update stock, and emit an event. A crash between steps can leave the world inconsistent.

A transaction gives a set of state transitions the all-or-nothing property: either every step commits or none do. It is the unit of atomicity.

## How

```text
BEGIN
  UPDATE accounts SET balance = balance - 100 WHERE user_id = 1
  UPDATE accounts SET balance = balance + 100 WHERE user_id = 2
  INSERT INTO ledger (id, from, to, amount) VALUES (...)
COMMIT
```

On commit, the database writes the transaction's intent to a durable write-ahead log (WAL) and applies the changes. On crash, recovery replays the WAL and either completes the committed transaction or rolls back the uncommitted one.

A transaction has four properties:

- **Atomicity** — all or nothing.
- **Consistency** — the state before and after obeys the business invariants.
- **Isolation** — concurrent transactions do not see each other's intermediate state, to the degree the isolation level promises.
- **Durability** — a committed transaction survives a crash.

## Under the hood

The mechanics that make commit reliable:

1. **Write-ahead logging** — log entries precede page writes. Log is durable before commit is acknowledged.
2. **Locks** — row, page, or table-level locks keep concurrent transactions from corrupting each other.
3. **MVCC** — instead of locking readers, the database keeps multiple versions. Readers see a snapshot; writers create new versions.
4. **WAL replay** — after a crash, the database replays committed log entries and undoes incomplete ones.

The isolation level decides how much isolation you get. Higher isolation means more locking or more version-checking, which hurts throughput.

## Production use cases

- Money movement with ledger entries.
- Multi-row updates for an order line.
- Flash-sale inventory decrement (see the flash-sale lesson).
- Multi-document consistency in a document store with explicit write rules.

## Trade-offs and failure modes

| Choice | Gains | Costs | Failure to watch |
|---|---|---|---|
| Short transactions | low lock contention | more code paths, retry logic | partial success across services |
| Long transactions | single place for all state | holds locks, blocks others | lock convoy |
| Single-node transaction | strong isolation | not available when the node is down | unavailable vs partitioned |
| Distributed transaction | cross-store consistency | two-phase-commit costs | in-doubt transactions |

## Observability

- Transactions per second, commit latency p50/p99.
- Lock wait and lock conflict counts.
- WAL size, fsync latency.
- Rollback fraction and cause.

## Lab

Write a transfer between two accounts that updates both balances and inserts a ledger row. Kill the process mid-transaction. Verify that on restart the database either applied the full transfer or none of it.

## Worked examples

**Situation: fund transfer, 1,000 transactions/second.**
Each transfer writes 2 balance rows + 1 ledger row. At 1,000 tps, that's 3,000 row-updates/second. With a 5 ms fsync, the WAL generation is `1,000 × 3 × 200 bytes = 600 KB/s`. If fsync is the bottleneck at 200 fsyncs/second, batching 5 transactions per fsync brings WAL fsync latency from 5 ms × 1,000 to 5 ms × 200 = 1,000 ms total — the WAL is now the rate limiter, not the CPU.

Crash recovery: a 30-second crash replays `30 × 1,000 = 30,000` log entries. At 10,000 entries/second replay speed, recovery takes 3 seconds. The 30-second crash window is the RPO target.

```text
WAL: LSN 1  LSN 2  LSN 3 ... COMMIT  LSN 4 ...
crash here ↑
replay: applies LSN 1-3, discards LSN 4+
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
