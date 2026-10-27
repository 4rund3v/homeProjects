# Reliability — in Depth

> The failure taxonomy, the two time-constants that define a reliability posture
> (MTBF/MTTR, RPO/RTO), and the single principle that turns reliability from a
> wish into a property: **make failures cheap and recoverable, not impossible.**

---

## 1. The failure taxonomy for this system

Every failure has a named mechanism that absorbs it. The list *is* the design:

```
   FAILURE                          MECHANISM THAT ABSORBS IT
   ───────────────────────────────  ──────────────────────────────────────
   API crashes mid-commit           nothing lost — committed or not
   Kafka down / slow                outbox queues durably; relay drains later
   Relay crashes mid-publish        duplicate event → idempotent consumer no-ops it
   Consumer crash mid-event         offset committed after DB write → reprocesses
   Poison message                   DLQ + alert; pipeline keeps moving
   Loan balance drifts              reconciliation detects → replay rebuilds
   Data grows unboundedly           partitioning + archival (drop, not delete)
   Bad deploy                       Helm rollback
   Node dies                        ⚠ NOT HANDLED — backups + documented RPO/RTO
```

**The principle behind the whole table:** *we don't try to stop the failure, we make
it cheap and recoverable.* That single reframe is the difference between a person who
says "we use redundancy" and one who names *which* mechanism catches *which* failure.

---

## 2. MTBF vs MTTR — the two time-constants

```
   MTBF — Mean Time Between Failures
     "How often does it break?"
     You can't drive this to zero. You CAN measure it and trend it.

   MTTR — Mean Time To Recovery
     "How long until it's back after breaking?"
     THIS is the one you engineer down.

   Reliability = MTBF / (MTBF + MTTR)

   → The lever is MTTR: runbooks, tested restores, rollbacks, automation.
     A system that breaks often but recovers in minutes is more available
     than one that breaks rarely but takes hours to recover.
```

**The discipline:** every alert needs a runbook
([`runbooks.md`](../runbooks.md)). An alert without a runbook is noise — it raises
your MTTR instead of lowering it.

---

## 3. RPO vs RTO — the two numbers you must state

```
   RPO — Recovery Point Objective
     "How much data can we lose?"
     For this project today: the WAL archive lag (seconds–minutes),
     because backups are off-box and WAL is continuously archived.
     → RPO ≈ last archived WAL segment

   RTO — Recovery Time Objective
     "How long to be back up?"
     = base backup copy + WAL replay. Minutes to tens of minutes.
     → the timed restore drill gives you this number

   The honest statement an interview wants:
     "Today RPO ≈ backup interval + WAL lag, RTO = restore time.
      I've run the restore drill and recorded RTO.
      Real HA (zero-downtime failover, RPO=0 for acked writes) needs
      a standby + quorum — that's the documented next step, not what
      I'm running."
```

**The rule:** never leave RPO/RTO unstated. An unstated RPO is an unstated
acceptance of data loss.

---

## 4. The three-tier reliability model (local vs prod)

```
   ┌──────────────────────────────────────────────────────────────────┐
   │  TIER 1 — CRASH RECOVERY (what you have now)                    │
   │    A pod restart / node reboot: Postgres replays WAL, continues.│
   │    This is NOT HA — the node itself is still the single point.  │
   ├──────────────────────────────────────────────────────────────────┤
   │  TIER 2 — DISASTER RECOVERY (backups + PITR)                    │
   │    Off-box base backup + WAL archive → restore to a point in    │
   │    time. RPO = archive lag, RTO = restore time.                 │
   ├──────────────────────────────────────────────────────────────────┤
   │  TIER 3 — LIVE HA (deferred, documented)                        │
   │    Standby + Patroni/etcd quorum + VIP. Auto-failover,          │
   │    RPO≈0 for acked writes. The path exists; not the runtime.   │
   └──────────────────────────────────────────────────────────────────┘

   The L5/L6 move: name which tier you're in and which tier the next one is.
   "I'm in Tier 2 with off-box PITR; Tier 3 is the documented next step."
```

---

## 5. The "make it cheap" moves that actually work

| Failure | The cheap-recovery move |
|---------|------------------------|
| Balance drift | balances are a **projection** of `balance_changes` → replay to rebuild |
| Lost a write | WAL is continuously archived → PITR to just before |
| Bad deploy | Helm rollback (one command, tested) |
| Kafka backlog | outbox drains automatically when the broker returns |
| Data loss on archival | verify-before-drop; the archive is independently restorable |

**The meta-move:** *the more of your state is reconstructible from a source of truth,
the cheaper every failure is.* Events are your source of truth; derived state
(balances) is a projection you can recompute. That's the whole reliability story in
one sentence.

---

## 6. The reliability interview answer (memorize the shape)

*"How do you keep this reliable when things fail?"*

```
  1. I don't try to prevent every failure — I make each one cheap and recoverable.
  2. Crash: Postgres replays WAL; the outbox absorbs a Kafka outage.
  3. Duplicates: the consumer is idempotent (event_id), so retry/replay is safe.
  4. Data integrity: a reconciliation job proves derived state matches source.
  5. Disaster: off-box base backup + continuous WAL archive → PITR; I've timed the
     restore drill.
  6. Stated limits: today RPO ≈ archive lag, RTO = restore time; live HA is the
     documented next step (standby + quorum).
  7. Fast recovery: every alert has a runbook, so MTTR stays low.
```

---

## 7. How this shows up here

- **Crash recovery** — the PVC keeps Postgres data across pod restarts; WAL replays.
- **Disaster recovery** — off-box `pg_dump` + WAL archive; the timed restore drill.
- **Rebuild-by-replay** — loan balances reconstructed from `balance_changes` / the Kafka
  log ([`data-lifecycle.md`](../data-lifecycle.md) §5).
- **Idempotency** — the `event_id` unique constraint is what makes replay safe.
- **Documented limits** — the single-node caveat and RPO/RTO in
  [`design.md`](../design.md) and [`infrastructure.md`](../infrastructure.md).
