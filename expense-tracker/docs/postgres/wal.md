# The Write-Ahead Log — WAL, Durability, Checkpoints

> If you learn one Postgres internal cold, learn this one. It's the answer to "how does
> Postgres survive a crash," "what does `synchronous_commit=off` actually risk," and half
> of every replication question. Mechanism first, then a single UPDATE traced to disk.

## Why a log at all

A crash can happen at *any* instruction. If Postgres wrote data pages directly to disk, a
half-applied change would leave the database **corrupt**, not merely stale. The fix is
write-ahead logging:

> **Before modifying a page in the buffer cache, append a record describing the change to
> a sequential log on disk. Acknowledge a commit only after that log record is durable.**

Recovery then becomes trivial: **replay the log** to bring pages up to date, or — for
changes whose commit record never made it — **undo/ignore** them. This is the same idea
behind Kafka's log, Raft's log, and every redo log in databases; Postgres calls it the
**WAL** (historically "xlog").

```
   the two copies of truth during normal operation:

     data files (random access, lazy)          WAL (sequential, eager)
     ┌───────────────────────────┐             ┌──────────────────────────┐
     │ page 3  ── (dirty)        │             │ LSN 100: update page 3   │
     │ page 7  ── clean          │  ◄──replay──│ LSN 128: update page 3   │
     │ page 9  ── (dirty)        │   on crash  │ LSN 156: COMMIT xid 500  │
     └───────────────────────────┘             │ LSN 160: update page 9   │
            flushed lazily                     └──────────────────────────┘
            at checkpoint                           flushed + fsynced
                                                    BEFORE commit ack
```

---

## LSNs — the log's coordinate system

Every WAL byte position has a **Log Sequence Number**, a 64-bit monotonic offset printed
like `0/1A3B4C5D`. LSNs are the unit of:
- **Durability**: "is LSN X flushed?" (`pg_current_wal_lsn()` vs `pg_last_wal_replay_lsn()`).
- **Replication**: a standby reports the LSN it has replayed; the lag is a difference of
  LSNs (see [`replication.md`](replication.md)).
- **Recovery**: "replay forward until LSN X" or "stop at this timeline/commit."
- **Backup**: `pg_backup_start`/`stop` record the LSN range a base backup covers.

You'll see LSNs in error messages, `pg_stat_replication`, and `pg_walfile_name(lsn)` —
learn to read them as *positions in one global log*.

---

## WAL files (segments) and their lifecycle

```
   pg_wal/
   ┌──────────────┬──────────────┬──────────────┬──────────────┐
   │ 000000010000│ 000000010000│ 000000010000│ 000000010000 │
   │ 000000000000│ 00000000000001│ 00000000000002│ ...          │
   │  (16MB each, │  002         │  003         │              │
   │   default)   │              │              │              │
   └──────────────┴──────────────┴──────────────┴──────────────┘
      being written   full, needed    recycled back    awaiting
      now             for recovery    to empty          archive/removal
```

- Default segment size is **16MB**; set at `initdb` (`--wal-segsize`), not changeable
  after. Bigger segments = fewer files, longer checkpoint/archive granularity.
- Files are **recycled**: once a segment's contents are older than the last checkpoint and
  no longer needed by replication or archiving, it's renamed and reused — hence
  `pg_wal` doesn't grow forever under steady load.
- `max_wal_size` is the *target* total; Postgres checkpoints to keep WAL under it.
- With `archive_mode=on`, a segment is only recyclable after the archiver has copied it
  to `archive_command`'s destination (see [`backup-restore.md`](backup-restore.md)).

---

## WAL record types (the ones that matter)

| Record | Written when | Why it exists |
|--------|--------------|---------------|
| Heap insert / update / delete | DML | the row change itself |
| **Full-page image (FPI)** | first touch of a page after a checkpoint | so replay can restore a torn/partial page |
| Page init / extend | new page allocated | |
| Transaction commit / abort | end of transaction | **the durability boundary** |
| Checkpoint | at checkpoint | a "everything before this LSN is on disk" marker |
| Running-xacts | periodically | snapshot reconstruction during recovery |
| Relcache / invalidation | DDL, catalog changes | |

**The FPI insight (a favorite interview follow-up):** if only the *delta* to a page were
logged, and the page's old on-disk image were torn (a crash mid-write), replay would
produce garbage. So the first WAL touch of each page after a checkpoint writes the **whole
8KB page image**. That's why the first write to a cold table after a checkpoint is
expensive, and why `checkpoint_completion_target` (spreading writes) matters.

---

## `wal_level`

| Value | Records | Use |
|-------|---------|-----|
| `minimal` | just enough for crash recovery | bulk load into a fresh table; no archiving, no PITR, no replication |
| `replica` (default since PG10) | enough for streaming replication + archiving | **what you want here** |
| `logical` | adds logical decoding info | needed for logical replication / CDC |

Setting `logical` adds WAL volume even if you never decode it. Set it only if you're
running a publication/subscription or a CDC pipeline.

---

## `synchronous_commit` — the durability dial

This is the single setting people most often misunderstand. It controls **when a COMMIT
acknowledges to the client relative to the WAL flush**, and each level trades a different
crash window.

```
   transaction timeline:
     ──[changes in shared_buffers]──[COMMIT record appended to WAL]──[ack to client]──

   synchronous_commit = on            (default)
     WAL is flushed+fsynced BEFORE the ack.
     ► crash after ack ⇒ change is on disk.  No data loss.
     ► every commit pays an fsync.

   synchronous_commit = remote_apply
     wait for sync standbys to flush AND apply, then ack.
     ► strongest; slowest; needs synchronous_standby_names.

   synchronous_commit = remote_write
     wait for sync standbys to have RECEIVED and written the WAL (not fsynced), then ack.
     ► survives loss of the local server, not necessarily a standby OS crash.

   synchronous_commit = local         (PG 11+)
     wait for the local WAL fsync, but do NOT wait for standbys.
     ► like `on` for a single node; different only with standbys.

   synchronous_commit = off
     ack WITHOUT waiting for the local fsync. The WAL record is in the OS/page cache
     and will be written "soon" (within wal_writer_delay, typically 200ms).
     ► crash of the POSTGRES PROCESS  ⇒ nothing lost (OS still has the cache).
     ► crash of the OS / power loss  ⇒ the last ~200ms of COMMITTED transactions
                                        may be LOST.
```

**The precise statement to make in an interview:** *`synchronous_commit=off` protects
against a Postgres process crash but not against an OS/power crash; the exposure window
is roughly `wal_writer_delay` (default 200ms). It is not "unsafe" — it's a documented
trade of a few hundred milliseconds of durability for much higher commit throughput, and
it's a legitimate choice for idempotent, replayable workloads.*

**For this project:** keep the default `on` for the request path that writes `expenses`
and the `outbox` — those are money events and the outbox's whole purpose is
never-lose-an-event. `off` is defensible for the consumer's `processed_events` bookkeeping
or bulk archival backfills, where a replay makes it harmless.

---

## Checkpoints

A **checkpoint** is the moment Postgres declares "all changes up to LSN L are now in the
data files." After a checkpoint, WAL before L is no longer needed for crash recovery
(only for archiving/replication).

```
   time ─────────────────────────────────────────────────────────────►

   writes:  ▁▁▂▃▅▇███████▇▅▃▂▁▁▁▂▃▅▇███████▇▅▃▂▁▁▁▂▃▅▇███████▇▅▃▂▁
                                              ▲ checkpoint
                                              │
   dirty pages in shared_buffers:             │
   ▁▁▂▃▅▇█████████████████████████▇▅▃▂▁▁▁▁   │  flushed during & after
                                              │  (spread by
                                              │   checkpoint_completion_target)
   WAL segments used:                          │
   ▁▁▂▃▅▇███████████████▇▅▃▂▁▁▁▁▁▁▁▁▁▁▁▁▁    │  recycled after checkpoint
                                              │
   FPI writes:      ▲ lots here (first touch  │
                    │  of pages post-checkpt) │
```

**The mechanics:**
- Triggered by `checkpoint_timeout` (default **5 min**) or when WAL exceeds `max_wal_size`.
- Writes a **checkpoint record** to WAL; recovery only replays from the last checkpoint.
- Dirty-page flushing is *spread* over the interval using `checkpoint_completion_target`
  (default 0.9 = spread over 90% of the interval) precisely to avoid an I/O spike.
- **Checkpoint storms** happen when writes are bursty: WAL hits `max_wal_size` early, a
  checkpoint fires, then the next burst hits again. Symptoms: latency spikes, a wall of
  FPI writes, `pg_stat_bgwriter.checkpoints_req` climbing (timed vs requested — requested
  is the bad one).

**Tuning levers** (see [`tuning-and-observability.md`](tuning-and-observability.md)):
raise `max_wal_size` so bursts fit inside one checkpoint cycle; keep
`checkpoint_completion_target` high (0.9) for smooth spreading; raise `checkpoint_timeout`
if you can tolerate longer recovery.

---

## Tracing one UPDATE to disk

Statement: `UPDATE loans SET outstanding = outstanding + 4250 WHERE id = 42;`

```
  step                          action                                     artifact
  ─────────────────────────────────────────────────────────────────────────────────
  1. parse/plan                cached plan for the prepared statement        (memory)
  2. acquire xid               next xid = 500                               (memory)
  3. locate row                index scan loans_pkey → TID (3,2)            (buffer cache)
  4. read page 3               miss in shared_buffers → OS cache → disk     (I/O if cold)
  5. build new tuple v2        in memory, xmin=500                          (memory)
  6. mark v1                   v1.xmax = 500                                (dirty page)
  7. WAL: heap update          LSN 0/100: "page 3 lp 2: old tuple → v2"
                               (+ FPI if first touch since checkpoint)      (WAL buffer)
  8. WAL: index updates        LSN 0/140: loans_pkey new entry (if idx col changed)
  9. COMMIT issued             LSN 0/160: "COMMIT xid 500"                  (WAL buffer)
 10. synchronous_commit=on     XLogFlush(0/160) → write(2) + fsync(2)       (DISK, fsync)
 11. ack to client             "UPDATE 1"                                   (network)
 12. later, at checkpoint      bgwriter flushes page 3 to the data file     (DISK, lazy)

  ► A crash between 11 and 12 is FINE: recovery replays WAL from the last checkpoint,
    redoing the page-3 change.
  ► A crash between 9 and 10: the commit record exists but isn't durable → treated as
    "did not commit" on recovery (with synchronous_commit=on this can't happen after ack).
  ► With synchronous_commit=off, a crash could lose step 9's record → the UPDATE is
    silently rolled back, even though the client was told it committed.
```

**Memorize the sequence:** *changes → WAL record → COMMIT record → fsync → ack → later
page flush.* Every durability question is "which of those boxes did we complete before
the crash?"

---

## WAL and the rest of the system

| Feature | How it uses WAL |
|---------|-----------------|
| **Streaming replication** | standby connects, receives WAL records, replays them |
| **Logical decoding** | `wal_level=logical`; a plugin turns WAL into row-level change streams |
| **PITR** | base backup + archived WAL segments replayed to a target (see [`backup-restore.md`](backup-restore.md)) |
| **Synchronous replication** | commit waits for standby WAL flush (see [`replication.md`](replication.md)) |
| **Two-phase commit** | `synchronous_commit=2pc` for PREPARE/COMMIT PREPARED durability |

---

## Interview angle

- **"What is the WAL and why is it needed?"** — sequential redo log written before data
  pages; makes recovery a replay and removes torn-page corruption.
- **"What does `synchronous_commit=off` risk?"** — the last ~`wal_writer_delay` ms of
  committed transactions on an OS/power crash; safe against a process crash.
- **"What's a checkpoint and why do they cause latency spikes?"** — the "everything
  before LSN L is on disk" marker; bursts of dirty pages + FPIs flushed together.
- **"What's a full-page image and why does it exist?"** — the first post-checkpoint WAL
  write of a page logs the whole page, so replay can survive a torn on-disk page.
- **"How does replication relate to WAL?"** — a standby replays the same WAL stream; lag
  is an LSN difference.
- **"How would you reduce checkpoint storms on a write-heavy workload?"** — raise
  `max_wal_size`, keep `checkpoint_completion_target` high, smooth the write rate, and
  watch `checkpoints_req` vs `checkpoints_timed`.

## How this shows up here

- The `expenses` + `outbox` write path keeps `synchronous_commit=on` — these are
  money events and the outbox's entire contract is "never lose an event"
  (see [`../event-flows.md`](../event-flows.md)).
- The consumer's `processed_events` insert can use `off` — a redelivery makes it
  idempotent, so a lost last-commit is harmless.
- `wal_level=replica` so we can add a standby later and run `pg_basebackup` for PITR.
- Watch `checkpoints_req` on the `balance_changes` write burst; raise `max_wal_size`
  before it becomes a latency problem.
- `max_wal_size` and friends are covered in
  [`tuning-and-observability.md`](tuning-and-observability.md); the recovery drill that
  *uses* archived WAL is in [`backup-restore.md`](backup-restore.md).
