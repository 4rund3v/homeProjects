# MVCC — Multi-Version Concurrency Control

> The reason Postgres can serve reads while writes happen, and the reason it needs
> vacuum. Mechanism first, then a row-by-row example on our `expenses` table.

## The core idea

Postgres never overwrites a row in place when you `UPDATE` it. Instead it writes a
**new row version** (a new *tuple*) and marks the old one as superseded. Readers see the
version that was visible **at the moment their transaction took its snapshot**; writers
append new versions. So:

> **Readers do not block writers, and writers do not block readers.**

This is the defining property of MVCC, and it's different from a lock-based engine
where a writer takes a lock that readers must wait on. The cost: old versions pile up
until vacuum removes them, and a reader may have to scan past several dead versions.

## Tuples, xmin, xmax

Every physical row (a *tuple*) carries hidden system columns:

| Column | Meaning |
|--------|---------|
| `xmin` | the transaction id (xid) that **inserted** this version |
| `xmax` | the xid that **deleted/updated** it (or `0` if still live) |
| `cmin`/`cmax` | command id within the transaction (rarely needed) |
| `ctid` | the physical location (page, offset) — a version can move |
| `tableoid`, `oid` | legacy/inheritance fields, ignore |

### Transaction IDs (xids)

An **xid** is a 32-bit counter that wraps. Each transaction gets one (or, for
read-only, borrows the current next-xid as its snapshot). Two properties matter:

- xids have a total **order** — that's how "did this commit before my snapshot?" is
  decided.
- Because they wrap, Postgres uses a special comparison (`TransactionIdPrecedes`) that
  treats the wraparound half of the circle as "older." This is why `freeze` exists
  (see [`vacuum-bloat.md`](vacuum-bloat.md)) — to stop the circle from running out.

### Visibility rules (simplified)

For a transaction with snapshot `S`, a tuple version `V` is **visible** if:

1. `V.xmin` **committed**, and `V.xmin` is "before" `S` (in the snapshot's list of
   in-progress or committed-before-start transactions), **and**
2. `V.xmax` is either `0`, **or** its transaction did **not** commit before `S`,
   **or** it aborted, **or** the deleter is our own transaction and we can see it.

Everything else — inserted by a concurrent uncommitted transaction, deleted by a
committed-later one — is invisible.

Concretely, `xmax` can hold more than a bare xid: it also encodes **tuple locks**
(`FOR UPDATE`/`FOR SHARE` markers) and **multi-xact** ids (when several transactions
hold a shared row lock). Those are details for [`locking-concurrency.md`](locking-concurrency.md).

## Snapshot isolation vs serializable

Postgres's default isolation is **READ COMMITTED**, but the read-committed snapshot is
taken **per statement**, not per transaction. In practice:

- **READ COMMITTED** — each *statement* sees a fresh snapshot. Two statements in the
  same transaction can see different data. No dirty reads (you never see uncommitted
  data). Non-repeatable reads and phantoms are possible.
- **REPEATABLE READ** — one snapshot for the whole transaction. No non-repeatable
  reads, no phantoms (for reads). But write skew is possible: two transactions read the
  same rows, each makes a locally-valid write, and together they violate a global
  invariant. You get a serialization failure only if the write conflicts directly.
- **SERIALIZABLE** — full serializability via **Serializable Snapshot Isolation
  (SSI)**: Postgres tracks read/write dependencies and aborts one transaction with a
  serialization failure (`40001`) when a dangerous structure (the write-skew pattern)
  appears. Retry the loser.

The full anomaly table lives in [`locking-concurrency.md`](locking-concurrency.md). The
MVCC-relevant point: **isolation level is a choice of snapshot + conflict detection**,
not a choice of locks.

## Visibility map and hint bits

Two mechanisms keep MVCC cheap enough to use:

### Hint bits

The tuple header has `HEAP_XMIN_COMMITTED` / `HEAP_XMAX_COMMITTED` **hint bits**. The
first transaction to inspect a tuple's xmin/xmax and find the status (from the commit
log / `clog`) **sets the bit**, so later readers don't re-consult the clog. This is a
write to the tuple header the first time, which generates a small WAL record and dirties
the page — the reason "a pure read can still write" (a favorite interview follow-up).

### Visibility map (VM)

A per-relation bitmap with **one bit per page**: "are all tuples on this page visible
to all current/future transactions?" (i.e. no dead tuples needing vacuum). When set:

- **Vacuum skips the page** — huge win for large mostly-static tables.
- **Index-only scans** can answer from the index alone when the all-visible bit is set
  (see [`indexes.md`](indexes.md) §Index-only scans).

Vacuum maintains the VM. This is why an under-vacuumed table loses both vacuum
efficiency and index-only-scan capability.

## Worked example: two transactions on one expense

```
   time ──────────────────────────────────────────────────────────────────────►

   Session A takes snapshot S_A (xmin=0, no concurrent writers yet)
   │
   │   ┌───────────────────── A: SELECT #1 ─────────────────────┐
   │   │  BEGIN;                                               │
   │   │  SELECT amount_cents FROM expenses WHERE id = 101;    │
   │   │   ► 4200  (sees tuple v1: xmin=T0, xmax=0)            │
   │   └────────────────────────────────────────────────────────┘
   │
   │        ┌────────────────── B: UPDATE ──────────────────────┐
   ├────────┤  BEGIN;                                           │
   │        │  UPDATE expenses SET note='checked' WHERE id=101; │
   │        │   ► appends tuple v2 (xmin=T_B)                   │
   │        │   ► sets   v1.xmax = T_B  (v1 now DEAD to future) │
   │        │  COMMIT;   (T_B now committed)                    │
   │        └────────────────────────────────────────────────────┘
   │
   │   ┌───────────────────── A: SELECT #2 ─────────────────────┐
   └───┤  SELECT amount_cents FROM expenses WHERE id = 101;     │
       │                                                         │
       │  READ COMMITTED:  fresh snapshot (now includes T_B)    │
       │   ► 4200  (sees tuple v2)                              │
       │                                                         │
       │  REPEATABLE READ: still S_A                            │
       │   ► 4200  (v2 is INVISIBLE — xmin T_B not in S_A)      │
       └────────────────────────────────────────────────────────┘

   Which version each snapshot sees for id=101:

     version   xmin    xmax     visible to S_A?   why
     ─────────────────────────────────────────────────────────────────────
       v1      T0      T_B          YES (S_A)     v1.xmax not committed
                                              at S_A; v1.xmin is old
       v2      T_B      0           NO  (S_A)     v2.xmin not in S_A
                                     YES (fresh)  T_B committed before it
```

Setup:

```sql
CREATE TABLE expenses (
  id          bigserial PRIMARY KEY,
  user_id     bigint NOT NULL,
  amount_cents bigint NOT NULL CHECK (amount_cents > 0),
  note        text,
  updated_at  timestamptz NOT NULL DEFAULT now()
);
INSERT INTO expenses (user_id, amount_cents) VALUES (7, 4200);  -- id = 101
```

Now two concurrent sessions:

```
Session A                                Session B
------------------------------------     ------------------------------------
BEGIN;                                   BEGIN;
SELECT amount_cents FROM expenses
 WHERE id = 101;                         UPDATE expenses
  --> 4200  (snapshot S_A: no                 SET note = 'checked'
        concurrent writer yet)              WHERE id = 101
                                          RETURNING amount_cents;
                                             --> updates: writes NEW tuple
                                                 (note='checked', xmin=T_B,
                                                  xmax on old = T_B), COMMIT
SELECT amount_cents FROM expenses
 WHERE id = 101;
  --> READ COMMITTED: new snapshot, sees
      the committed new version. Same
      transaction, different answer.
      In REPEATABLE READ this second
      SELECT still returns 4200 (old
      snapshot) and never sees the change.
COMMIT;
```

What's physically happening:

- The `UPDATE` **appends** a new tuple version; the old one is not erased, its `xmax`
  is set to `T_B`.
- Session A's first read saw the old version (correct per its snapshot). Its second
  read, in READ COMMITTED, takes a fresh snapshot and sees the new version.
- The old version is now a **dead tuple**. It stays until **vacuum** proves no
  snapshot still needs it. Vacuum's entire job exists because of this paragraph.

## The cost of keeping versions

1. **Bloat** — dead tuples occupy pages and indexes until vacuumed
   ([`vacuum-bloat.md`](vacuum-bloat.md)).
2. **Longer scans** — a seq scan walks past dead tuples; an index scan finds the first
   visible version, which may require heap checks.
3. **Long transactions are toxic** — a transaction holding an old snapshot pins *all*
   versions that existed at its start. One forgotten `BEGIN; SELECT ...` open for an
   hour can pin an hour of dead tuples, defeating autovacuum. **The #1 operational
   MVCC bug is a long-running transaction.** Find them with `pg_stat_activity`.

## `SELECT ... FOR UPDATE` and MVCC

Row locks are a *separate* layer from MVCC visibility:

- MVCC decides **what you can see**.
- `FOR UPDATE` decides **who may write next**, by locking the **latest version** of the
  row (not the version your snapshot sees).

So in the example: if Session A ran `SELECT ... FOR UPDATE` **before** B committed, A
waits for B; when B commits, `FOR UPDATE` **re-evaluates** the row against A's (READ
COMMITTED) fresh snapshot and locks the new version. In REPEATABLE READ, a row that was
updated concurrently instead **errors** (`could not serialize access due to concurrent
update`) rather than silently locking the new version.

This interaction is exactly what makes the loan-balance consumer correct — see
[`locking-concurrency.md`](locking-concurrency.md) §The loan-balance row lock.

## Interview angle

- **"Why don't readers block writers in Postgres?"** — MVCC: writers append new tuple
  versions; readers use a snapshot to pick the right version. Contrast with a
  lock-based DB (or SQL Server's default, which historically used locks for reads).
- **"What's the downside?"** — dead-tuple accumulation, bloat, the need for vacuum, and
  long-transaction hazards.
- **"Can a pure read write to disk?"** — Yes: hint bits and the visibility map get
  updated, producing WAL. Good catch if you say it.
- **"How do hint bits and the VM reduce MVCC cost?"** — cache clog lookups; let vacuum
  skip clean pages; enable index-only scans.
- **"Isolation level vs MVCC?"** — MVCC is the mechanism; isolation level chooses the
  snapshot scope and conflict detection (READ COMMITTED / RR / SSI).

## How this shows up here

- The consumer's `SELECT ... FOR UPDATE` on `loans` locks the latest version, so
  concurrent `ExpenseRecorded` events for the same loan serialize instead of racing.
- The outbox relay uses `FOR UPDATE SKIP LOCKED` so multiple replicas pull disjoint
  rows — see [`locking-concurrency.md`](locking-concurrency.md) §SKIP LOCKED.
- We keep transactions **short** (no idle-in-transaction) precisely so vacuum can keep
  up on `outbox` and `balance_changes`.
