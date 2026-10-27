# Database isolation levels

[Back](../../README.md)

## Why

Concurrency in a database is not all-or-nothing. The isolation level chooses how much interference a transaction tolerates. The choice between levels is a trade between throughput and predictability.

## How

SQL standard levels, from weakest to strongest:

| Level | What is prevented |
|---|---|
| Read Uncommitted | dirty reads |
| Read Committed | uncommitted values |
| Repeatable Read | non-repeatable reads, phantom reads (implementation dependent) |
| Serializable | all interleavings that break the invariants |

Most engines default to Read Committed.

## Under the hood

Each level changes the visibility rules and the amount of locking the engine must hold.

- **Read Committed** — a read sees the latest committed version. Two reads of the same row in the same transaction can differ.
- **Repeatable Read** — a transaction pins a snapshot. Reads see one consistent view. Some databases still allow write skew.
- **Serializable** — the engine must prevent all dangerous interleavings. It often uses predicate locks or detects conflicts and aborts transactions.

### Write skew

Two transactions read the same data, each decides based on that read, and both commit. The system invariant is broken even though each transaction saw a consistent snapshot. Serializability prevents this by detecting the conflict and aborting one.

```text
T1 reads total seats remaining = 10, requests 5
T2 reads total seats remaining = 10, requests 5
Both commit. Now the system has 15 seats remaining.
```

## Production use cases

- Money movement: serialize on the affected rows, or use repeatable read with careful conflict detection.
- Reporting: read committed is enough; readers never block writers.
- Flash sales: serialize, or use optimistic version checks.

## Trade-offs

| Level | Cost | Safety |
|---|---|---|
| Read Uncommitted | lowest | dirty reads |
| Read Committed | low | non-repeatable reads |
| Repeatable Read | medium | write skew |
| Serializable | high | safe, more aborts |

## Observability

- Abort count by isolation level.
- Lock wait time.
- Write-skew detector: a background invariant checker that reads the business rule and verifies the state.

## Lab

At Read Committed, run two transactions that both read a counter and both write. Observe lost updates. At Serializable, observe the aborts. Measure the trade-off.

## Worked examples

**Situation: 1,000 concurrent flash-sale reservations, 100 tickets.**
At Read Committed: all 1,000 read "100 available" at t=0, all 1,000 write → oversell by 900. At Serializable: the engine detects the write-skew (two transactions both read 100, both write 1) and aborts 900 of the 1,000. Retry with exponential backoff (base 10 ms, max 500 ms, 10 retries): ~5% of requests still fail after 10 retries. The p99 latency at Serializable is ~15 ms vs 2 ms at Read Committed. The 7.5× latency cost is the price of the oversell guarantee.

```text
RC:   1000 readers → all see 100 → all write → oversell
SER:  1000 readers → engine aborts 900 → retry → 100 succeed
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
