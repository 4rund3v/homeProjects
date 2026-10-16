# Locking & Concurrency — Isolation, Locks, Deadlocks

> How Postgres decides "who goes next," the anomaly table that explains every isolation
> level, the lock compatibility matrix, and the three `FOR UPDATE` clauses this project's
> consumer and relay depend on. Mechanism first, then the loan-balance row lock.

## Two different systems: MVCC vs locks

Everything in Postgres concurrency is two cooperating layers, and conflating them is the
most common interview mistake:

```
   ┌─────────────────────────────────────────────────────────────────┐
   │  MVCC  — decides WHAT YOU SEE                                    │
   │    snapshot taken at BEGIN (RR) or per-statement (RC)            │
   │    readers never block, never wait, never lock                    │
   ├─────────────────────────────────────────────────────────────────┤
   │  LOCKS — decides WHO MAY WRITE NEXT                              │
   │    taken only by writers and by explicit FOR UPDATE              │
   │    a lock CAN block and CAN deadlock                             │
   └─────────────────────────────────────────────────────────────────┘
```

A plain `SELECT` takes no locks. A plain `UPDATE` takes a **row lock on the latest
version** (via `xmax`), not a durable named lock you can see in `pg_locks` for long.
`SELECT ... FOR UPDATE` converts a read into an explicit write lock. That's the whole
game (mechanism in [`mvcc.md`](mvcc.md)).

---

## Isolation levels and the anomaly table

The four classic anomalies, in increasing subtlety:

| Anomaly | What goes wrong | Who prevents it |
|---------|-----------------|-----------------|
| **Dirty read** | T2 reads T1's *uncommitted* write | nobody in Postgres — never possible |
| **Non-repeatable read** | T2 re-reads a row and gets a *different* value | REPEATABLE READ and up |
| **Phantom read** | T2 re-runs a range query and sees *new* rows | SERIALIZABLE for full protection |
| **Write skew** | two txns each read overlapping data, each makes a locally-valid write, together they break a global invariant | SERIALIZABLE (SSI) |
| **Lost update** | read-modify-write races: both read 100, both write 101, one increment vanishes | `FOR UPDATE`, atomic `UPDATE ... SET x = x + 1`, or SERIALIZABLE |

The full matrix:

| Isolation level | Dirty | Non-repeatable | Phantom | Write skew | Lost update |
|-----------------|-------|----------------|---------|------------|-------------|
| READ UNCOMMITTED | *not offered* — Postgres treats it as READ COMMITTED | | | | |
| **READ COMMITTED** (default) | ✗ prevented | possible | possible | possible | possible |
| **REPEATABLE READ** | ✗ prevented | ✗ prevented | ✗ prevented* | **possible** | prevented on direct update |
| **SERIALIZABLE** | ✗ prevented | ✗ prevented | ✗ prevented | ✗ prevented | ✗ prevented |

\* In Postgres, REPEATABLE READ prevents phantoms for *reads* (snapshot isolation), but
the write-side holes (write skew, read-only anomaly) remain.

### The write-skew example (why RR is not enough)

The canonical case, on our schema — "a loan may not be overdrawn beyond its limit":

```
   loans:  id=42, outstanding=0, credit_limit=1000

   T1: BEGIN ISOLATION LEVEL REPEATABLE READ;
       SELECT outstanding FROM loans WHERE id=42;      -- reads 0
       -- decides: adding 900 is fine (0 + 900 ≤ 1000)

   T2: BEGIN ISOLATION LEVEL REPEATABLE READ;
       SELECT outstanding FROM loans WHERE id=42;      -- reads 0  (same snapshot!)
       -- decides: adding 800 is fine (0 + 800 ≤ 1000)

   T1: UPDATE loans SET outstanding = 900 WHERE id=42; COMMIT;
   T2: UPDATE loans SET outstanding = 800 WHERE id=42; COMMIT;
                                                                  ── 1700 > 1000.
   Neither transaction saw the other; each write was "correct" given its snapshot.
   REPEATABLE READ ALLOWS THIS. The invariant is broken.
```

Under **SERIALIZABLE**, Postgres's SSI tracks that T1 and T2 both *read* the row the
other *wrote* — a dangerous structure — and aborts one with `40001`. Your app must
**retry**.

---

## Serializable Snapshot Isolation (SSI)

Postgres implements serializable isolation not with locks but with **conflict
detection**:

- Every transaction keeps its snapshot; reads and writes are tracked as **predicate
  locks** and **read/write dependencies** (`SIREAD` locks — internal, not the row locks
  you see in `pg_locks`).
- When the runtime detects a **dangerous structure** — roughly, "T1 read something T2
  wrote, T2 read something T1 wrote, forming a cycle with no commit order that could
  produce it" — it aborts one transaction.
- The error is `ERROR: could not serialize access due to read/write dependencies among
  transactions` with SQLSTATE **40001**.

**The contract you must implement:** every SERIALIZABLE transaction needs a **retry
loop**. 40001 is not a bug; it's the mechanism telling you to rerun the transaction with
a fresh snapshot.

```python
def transfer(from_id, to_id, cents):
    for attempt in range(5):
        try:
            with transaction.atomic():          # SET TRANSACTION ISOLATION LEVEL SERIALIZABLE
                src = lock_account(from_id)     # SELECT ... FOR UPDATE
                dst = lock_account(to_id)
                if src.balance_cents < cents:
                    raise InsufficientFunds()
                src.balance_cents -= cents
                dst.balance_cents += cents
            return
        except SerializationFailure:
            sleep(backoff(attempt))             # 40001 → retry the WHOLE transaction
    raise TooMuchContention()
```

**When to use SERIALIZABLE here:** the loan-balance invariant. If two `ExpenseRecorded`
events could ever interleave such that `outstanding + new` exceeds `credit_limit`, and
the check happens in the app, SERIALIZABLE is the correct guarantee. The cheaper
alternative — a `CHECK` constraint plus `FOR UPDATE` — covers most cases and is what
this project uses (see below).

---

## Lock types

| Scope | Taken by | Granularity | Notes |
|-------|----------|-------------|-------|
| **Row (tuple) lock** | `UPDATE`/`DELETE`, `FOR UPDATE` | one tuple version | stored in `xmax`; invisible as a long-lived `pg_locks` row |
| **Tuple lock** | concurrent updaters of the same row | one tuple | coordinates *who waits*, released at txn end |
| **Page lock** | rarely explicit | one 8KB page | internal |
| **Relation (table) lock** | DDL, `LOCK TABLE`, some DDL-adjacent DML | whole table | the compatibility matrix below |
| **Advisory lock** | `pg_advisory_lock()` | an app-chosen 64-bit key or two 32-bit ints | Postgres doesn't know what it means; you do |
| **Transactionid / virtualxid** | every txn internally | one xid | used for wait-for graphs and deadlock detection |

**Row locks are taken on the LATEST version, not the version you read.** That's the
subtlety in [`mvcc.md`](mvcc.md) §`FOR UPDATE`: under READ COMMITTED, if the row was
updated concurrently, your `FOR UPDATE` waits, then re-evaluates and locks the new
version. Under REPEATABLE READ, the same situation is a hard error
(`could not serialize access due to concurrent update`, SQLSTATE **40001**) — because
re-evaluating against a new version would break your snapshot.

---

## The lock compatibility matrix

This table answers "can these two requests run at the same time?" — the single most
useful thing to have memorized.

**Row-level locks:**

| Requested \ Held | FOR KEY SHARE | FOR SHARE | FOR NO KEY UPDATE | FOR UPDATE |
|------------------|:-------------:|:---------:|:-----------------:|:----------:|
| **FOR KEY SHARE** | ✓ | ✓ | ✓ | ✗ |
| **FOR SHARE** | ✓ | ✓ | ✗ | ✗ |
| **FOR NO KEY UPDATE** | ✓ | ✗ | ✗ | ✗ |
| **FOR UPDATE** | ✗ | ✗ | ✗ | ✗ |

`FOR KEY SHARE` is the weakest: it only blocks changes to the **key** columns, so a plain
`UPDATE` of a non-key column can proceed — that's why FK checks use it (a referencing row
can be inserted without blocking updates to the referenced row's other columns).

**Table-level locks** (the ones that matter):

| Requested \ Held | ACCESS SHARE | ROW SHARE | ROW EXCL | SHARE | SHARE ROW EXCL | EXCL | ACCESS EXCL |
|------------------|:------------:|:---------:|:--------:|:-----:|:--------------:|:----:|:-----------:|
| **ACCESS SHARE** (SELECT) | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| **ROW SHARE** (`SELECT FOR UPDATE`) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| **ROW EXCLUSIVE** (`UPDATE`/`INSERT`/`DELETE`) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| **SHARE** | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ |
| **ACCESS EXCLUSIVE** (`ALTER TABLE`, `DROP`) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |

The two rows to internalize:

- **`UPDATE` (ROW EXCLUSIVE) does not block `SELECT` (ACCESS SHARE).** MVCC is why —
  readers never lock. This is the headline property.
- **`ALTER TABLE` (ACCESS EXCLUSIVE) blocks everything, including plain reads.** A
  migration that rewrites a table stops all traffic to it. This is why migrations need
  `lock_timeout` and why [`../postgres-guide.md`](../postgres-guide.md) §7 mandates
  expand/contract.

```
   what a naive ALTER TABLE does to a busy table:

   requests:  ████████████████████████████░░░░░░░░░░████████████████
                                       ▲          ▲
                            ALTER takes ACCESS EXCLUSIVE
                            everyone queues behind it until it finishes
```

---

## Deadlocks

A deadlock is a **cycle in the wait-for graph**: T1 holds A wants B, T2 holds B wants A.

```
   T1                              T2
   ─────────────────────────       ─────────────────────────
   UPDATE accounts SET ...          UPDATE accounts SET ...
     WHERE id = 1;  ──holds 1──►      WHERE id = 2;  ──holds 2──►
   UPDATE accounts SET ...
     WHERE id = 2;  ──wants 2──►      WHERE id = 1;  ──wants 1──►
                    └────────────── cycle ──────────────┘

   Postgres detects it and picks a VICTIM:
     ERROR: deadlock detected
     DETAIL: Process 1234 waits for ShareLock on transaction 5678;
             blocked by process 5678.
             Process 5678 waits for ShareLock on transaction 1234;
             blocked by process 1234.
```

**The mechanics:**

- Postgres runs the deadlock detector every **`deadlock_timeout`** (default **1s**). A
  transaction blocked longer than that is checked for a cycle.
- When a cycle is found, the transaction that has done the **least work** (by its own
  counter) is aborted. The other proceeds.
- The victim gets SQLSTATE **40P01**. **Retry it.**

**Why the 1s timeout matters:** a deadlock that resolves in under a second isn't
detected as a deadlock at all — one side just waits. Lowering `deadlock_timeout` detects
sooner (more CPU on the detector); raising it hides short deadlocks but risks longer
stalls. On this single node, the default is fine.

**The fix — acquire locks in a canonical order.** Always lock accounts by ascending
`id`. Then T1 wants {1,2} and T2 wants {1,2}, and the second one simply waits for the
first to finish. No cycle is possible:

```
   both transactions lock in ascending id order:

   T1: lock 1 ✓ → lock 2 (waits)
   T2: lock 1 (waits) ...

   wait-for graph: T1 → T2  (a chain, not a cycle)  → no deadlock, just a wait
```

---

## `FOR UPDATE`, `FOR SHARE`, and `SKIP LOCKED`

```sql
SELECT ... FROM t WHERE ... FOR UPDATE [OF t] [NOWAIT | SKIP LOCKED];
```

| Clause | Lock taken | Blocks other | Use |
|--------|-----------|--------------|-----|
| `FOR UPDATE` | strongest row lock | all row writers, `FOR SHARE`, `FOR KEY SHARE` writers | read-modify-write |
| `FOR SHARE` | shared row lock | other `FOR SHARE`-holders from writing | read-validate, allow others to read |
| `FOR NO KEY UPDATE` | weaker — allows `FOR KEY SHARE` | most writers | FK checks |
| `FOR KEY SHARE` | weakest | only key changes | FK checks from the referencing side |
| `NOWAIT` | error immediately instead of waiting | — | fail fast, don't queue |
| `SKIP LOCKED` | **skip rows already locked** | — | work queues, multi-consumer |

### The loan-balance row lock

The consumer processes `ExpenseRecorded` events. Two events for the **same loan** can
arrive concurrently (different partitions can't be ordered across, and the relay may
publish in an unexpected order):

```sql
BEGIN;
SELECT outstanding FROM loans WHERE id = 42 FOR UPDATE;   -- lock the loan row
-- app computes: new_outstanding = outstanding + amount_cents
UPDATE loans SET outstanding = new_outstanding WHERE id = 42;
INSERT INTO balance_changes (loan_id, delta_cents, event_id) VALUES (...);
INSERT INTO processed_events (event_id) VALUES (...);      -- idempotency gate
COMMIT;
```

**Why `FOR UPDATE` and not a plain `UPDATE ... SET outstanding = outstanding + X`:**

```
   without FOR UPDATE (read-then-write race):

   T1: SELECT outstanding  ──► 1000
   T2: SELECT outstanding  ──► 1000     (both read the same value)
   T1: UPDATE ... = 1000 + 4250  ──► 4250
   T2: UPDATE ... = 1000 + 1800  ──► 2800   ── T1's change LOST (last write wins)
```

The atomic form `SET outstanding = outstanding + 4250` avoids *that* specific race —
Postgres re-reads the current row version when applying the increment. But it can't
enforce a **cross-row invariant** ("outstanding must never exceed credit_limit") or
append a `balance_changes` row that matches, because the check and the write are
separate statements. `FOR UPDATE` makes the read-modify-write **atomic as a unit**:

```
   with FOR UPDATE:

   T1: SELECT ... FOR UPDATE  ──► 1000  (holds the row lock)
   T2: SELECT ... FOR UPDATE  ──► BLOCKS (waits for T1)
   T1: UPDATE outstanding = 4250;  INSERT balance_changes;  COMMIT;
   T2: (unblocks, re-reads) ──► 4250; UPDATE = 4250 + 1800 = 6050; COMMIT;
                                          ── both increments preserved, in order
```

This is why [`../event-flows.md`](../event-flows.md) specifies `FOR UPDATE` on the
consumer path, and why the Kafka **partition key is `loan_id`** — events for one loan are
already serialized by Kafka, so the row lock is a *belt-and-braces* guard against the
relay publishing out of order or a duplicate delivery racing itself.

### `FOR UPDATE SKIP LOCKED` — the multi-replica relay

The outbox relay is idempotent and may run in multiple replicas for throughput. Without
coordination, both replicas would grab the same unpublished rows and publish duplicates.

```
   3 relay replicas, one outbox table:

   ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
   │  relay A     │      │  relay B     │      │  relay C     │
   └──────┬───────┘      └──────┬───────┘      └──────┬───────┘
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                ▼
              SELECT id FROM outbox
               WHERE published_at IS NULL
               ORDER BY produced_at
               FOR UPDATE SKIP LOCKED
               LIMIT 100;
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
   A gets rows 1,4,7,...   B gets 2,5,8,...   C gets 3,6,9,...
   (each row locked by exactly one replica; the others SKIP it)
```

The sequence:

1. A runs the query and **locks** the rows it returned (until its transaction ends).
2. B runs the same query; rows A holds are **skipped**, not waited on. B gets a
   *disjoint* set.
3. Each replica publishes its rows to Kafka, then `UPDATE outbox SET published_at=now()`
   and commits — releasing the locks.

**Why not `FOR UPDATE` (blocking)?** B would wait for A's whole transaction, serializing
the replicas — you'd get one replica's throughput with three replicas' cost.
**Why not no lock at all?** Both would process the same rows, publishing duplicate
events. (Harmless here, since the consumer is idempotent — but wasteful, and it makes
the outbox depth metric lie.)

**The caveat:** the lock lives until the transaction ends. So the publish work must
happen **inside** the transaction, or you hold row locks across a Kafka round-trip. The
relay therefore runs `BEGIN → SELECT SKIP LOCKED → publish → UPDATE published_at →
COMMIT`, accepting that a slow Kafka publish extends the lock window. Alternative: a
`claimed_by`/`claimed_at` column updated first (a lease), no row lock held during the
publish — better for slow brokers, at the cost of handling crashed claimers.

---

## Advisory locks

A lock on an **arbitrary 64-bit key** you choose. Postgres enforces mutual exclusion but
knows nothing about what the key means.

```sql
-- session-level (held until released or session ends)
SELECT pg_advisory_lock(hashtext('archival-job'));

-- transaction-level (auto-released at COMMIT/ROLLBACK) — usually what you want
SELECT pg_try_advisory_lock(hashtext('archival-job'));   -- returns false if held

-- xact-scoped shared lock, for "many readers, one writer"
SELECT pg_advisory_xact_lock_shared(key);
```

**Use here:** the archival job ([`../data-lifecycle.md`](../data-lifecycle.md)) must not
run twice concurrently. A transaction-scoped advisory lock on a well-known key makes the
second instance's `pg_try_advisory_lock` return `false`, so it exits immediately — no
queueing, no polling table, no cron race.

**Caveat under PgBouncer transaction pooling:** advisory locks are session-scoped by
default; always use the `pg_advisory_xact_*` variants so the lock is tied to the
transaction, not the pooled server connection (see
[`tuning-and-observability.md`](tuning-and-observability.md) §PgBouncer).

---

## `pg_locks` — seeing what's blocked

The modern way to answer "who is blocking this?" without walking `pg_locks` by hand:

```sql
SELECT blocked.pid            AS blocked_pid,
       blocked.query          AS blocked_query,
       blocking.pid           AS blocking_pid,
       blocking.query         AS blocking_query,
       now() - blocked.query_start AS waited_for
FROM pg_stat_activity AS blocked
CROSS JOIN LATERAL unnest(pg_blocking_pids(blocked.pid)) AS b(pid)
JOIN pg_stat_activity AS blocking ON blocking.pid = b.pid
WHERE cardinality(pg_blocking_pids(blocked.pid)) > 0;
```

`pg_blocking_pids(pid)` walks the wait-for graph for you. Learn this query — it's the
first thing you run when the consumer stalls.

---

## Interview angle

- **"Difference between optimistic and pessimistic locking?"** — optimistic: MVCC +
  retry on 40001 (no lock held during the read). Pessimistic: `FOR UPDATE`, wait now.
  Postgres gives you both; pick by contention level.
- **"Design a deadlock-free bank transfer."** — lock accounts in ascending `id` order,
  or use `SELECT ... FOR UPDATE` on both rows in one statement ordered by id. Mention
  retrying 40P01 anyway, because deadlocks can still arise from index-order surprises.
- **"Does `UPDATE` block `SELECT`?"** — no (ROW EXCLUSIVE vs ACCESS SHARE, and MVCC
  means readers don't lock). But `ALTER TABLE` does.
- **"What does SERIALIZABLE cost you?"** — SSI overhead plus a mandatory retry loop on
  40001. Throughput drops under write-write contention; that's the price of correctness.
- **"How do you run a single job exactly once?"** — `pg_try_advisory_xact_lock` on a
  well-known key.
- **"How do N workers share a queue table without double-processing?"** —
  `FOR UPDATE SKIP LOCKED LIMIT k`.

---

## How this shows up here

- The consumer's `SELECT ... FOR UPDATE` on `loans` makes the read-compute-write atomic
  and preserves ordering across duplicate deliveries
  ([`../event-flows.md`](../event-flows.md)).
- The relay's `FOR UPDATE SKIP LOCKED` lets relay replicas scale without duplicating
  publishes.
- The archival job uses `pg_try_advisory_xact_lock` to guarantee a single runner
  ([`../runbooks.md`](../runbooks.md)).
- We stay in **READ COMMITTED** for the API path (per-statement snapshots are fine for
  independent expense writes) and reserve **SERIALIZABLE** for any future
  cross-account invariant, where a `CHECK` constraint isn't expressible.
- Long transactions are treated as a bug (see [`vacuum-bloat.md`](vacuum-bloat.md)); the
  relay's lock window is the one place we accept a longer transaction deliberately.
