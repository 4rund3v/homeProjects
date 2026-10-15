# Runbooks

> Every alert and routine operation gets a runbook: **what it means, the first thing
> to check, and how to fix it.** An alert without a runbook is noise. Fill these in
> during Phase 12 (trip each alert on purpose and write its entry).

**Format per runbook:** Symptom · Likely cause(s) · First thing to check · Fix · How to
verify it's fixed · Escalation/notes.

---

## Incident runbooks (alerts)

### RB-01 — Kafka consumer lag rising
- **Means:** the loan-update consumer is falling behind; balances are going stale.
- **First check:** consumer pod health and logs; is it erroring or just slow? Check
  ingress vs egress rates ([`observability.md`](observability.md) §5).
- **Fix:** if erroring on a poison message, confirm it hit the DLQ and the loop
  continued. If just slow, scale consumers up to the partition count, or investigate
  the slow DB writes.
- **Verify:** lag drains back to ~0.
- **Notes:** lag is the #1 signal that loan balances are wrong. Alert threshold and
  duration: ____.

### RB-02 — Outbox depth / age rising
- **Means:** the relay can't publish; Kafka may be down or a poison message is stuck.
- **First check:** Kafka broker health; the relay's logs; the oldest unsent row's
  `attempts`.
- **Fix:** if Kafka is down, wait for recovery — the outbox drains automatically. If a
  row has maxed `attempts`, route it to the DLQ and investigate the payload.
- **Verify:** outbox depth returns to baseline.
- **Notes:** the API keeps accepting expenses while this happens — that's the outbox
  working. But don't let depth grow unbounded (disk).

### RB-03 — DLQ depth > 0
- **Means:** a message couldn't be processed after retries.
- **First check:** the DLQ message contents; what's malformed?
- **Fix:** fix the producer/schema or the data; replay the message from the DLQ.
- **Verify:** DLQ drains; no new arrivals.
- **Notes:** any sustained DLQ depth needs a human. Don't auto-delete.

### RB-04 — API 5xx rate spike
- **Means:** your bug or a dependency failure.
- **First check:** API logs by endpoint and status; DB connectivity; recent deploys.
- **Fix:** roll back the latest deploy if it correlates; otherwise fix forward.
- **Verify:** 5xx rate returns to baseline.
- **Notes:** separate 4xx (often client error) from 5xx (your bug) in the alert.

### RB-05 — API p99 latency high
- **Means:** degradation users feel.
- **First check:** traces for the slow span; `pg_stat_statements` for a slow query;
  connection pool saturation.
- **Fix:** optimize the query, add the index, or scale out.
- **Verify:** p99 returns under threshold.
- **Notes:** never alert on mean latency; the tail is what matters.

### RB-06 — DB connections near max
- **Means:** pool exhaustion; PgBouncer or `max_connections` misconfigured.
- **First check:** connection count vs max; is PgBouncer in front? Pool settings.
- **Fix:** add/verify PgBouncer transaction pooling; tune pool sizes; kill idle
  connections.
- **Verify:** connection count stable, well under max.
- **Notes:** remember the PgBouncer transaction-mode caveats
  ([`postgres-guide.md`](postgres-guide.md) §4).

### RB-07 — Cache hit ratio dropping
- **Means:** memory/IO problem; queries hitting disk.
- **First check:** recent query changes; `shared_buffers` vs available RAM; seq scans
  climbing.
- **Fix:** add missing indexes; tune `shared_buffers`; reduce working set.
- **Verify:** cache hit ratio back above ~0.99 warm.
- **Notes:** a sudden drop usually follows a new un-indexed query.

### RB-08 — Dead tuples / bloat climbing
- **Means:** vacuum falling behind on a hot table.
- **First check:** `n_dead_tup` vs autovacuum thresholds; last autovacuum time.
- **Fix:** lower `autovacuum_vacuum_scale_factor` for the hot table; if deletes are the
  cause, switch to partition drops ([`data-lifecycle.md`](data-lifecycle.md) §3).
- **Verify:** dead tuples plateau; table size stops growing.
- **Notes:** never disable autovacuum; tune it.

### RB-09 — Reconciliation drift detected
- **Means:** a loan's `outstanding` != sum of its balance changes — data integrity
  issue.
- **First check:** which loan(s); recent consumer errors or deploys around the drift
  window.
- **Fix:** run the rebuild-from-archive path for the affected loan(s)
  ([`data-lifecycle.md`](data-lifecycle.md) §5).
- **Verify:** reconciliation passes; balance matches the event sum.
- **Notes:** this is the self-healing trigger. Treat drift seriously — find the root
  cause (a missed event? a bad deploy?) not just the symptom.

### RB-10 — Archive job failed
- **Means:** the lifecycle automation didn't run or errored; a partition may not have
  been archived/dropped.
- **First check:** the CronJob logs; disk space; the partition it was processing.
- **Fix:** re-run the archive step; **verify the copy before dropping** anything.
- **Verify:** the archive exists and is verified; the partition is dropped only after.
- **Notes:** a failed archive must block the partition drop — never drop unverified.

### RB-11 — TLS cert nearing expiry
- **Means:** the edge cert will expire.
- **First check:** cert expiry date; the renewal mechanism.
- **Fix:** renew; if automated (e.g. cert-manager), check its logs.
- **Verify:** new expiry date; TLS handshake works over Tailscale.
- **Notes:** alert well before expiry, not on it.

### RB-12 — Rate-limit 429 spike
- **Means:** abuse, a misbehaving client, or a too-tight limit.
- **First check:** is it NGINX (per-IP) or DRF (per-user)? Which source?
- **Fix:** if legitimate traffic, tune the limit; if abuse, the limit is working.
- **Verify:** legitimate traffic unaffected; abuse blocked.
- **Notes:** distinguish the two 429 sources ([`infrastructure.md`](infrastructure.md) §5).

---

## Routine operations

### RO-01 — Deploy a new version
1. Build and push a new image tag.
2. `terraform plan` — read the diff (image tag change).
3. `terraform apply` (or `helm upgrade` if deploying the app outside Terraform — pick
   one path and be consistent).
4. Watch the rolling update; confirm probes pass and no 5xx spike.
5. If it degrades: `helm rollback` / revert the tag and re-apply.

### RO-02 — Run a schema migration
1. Review the migration; confirm it's expand/contract safe
   ([`postgres-guide.md`](postgres-guide.md) §7).
2. Test against a production-sized dataset — timing matters.
3. Apply via the deploy pipeline, never by hand on the server.
4. Verify the schema and that the app still works.

### RO-03 — Archive a partition (manual)
1. Detach the target partition.
2. Export to Parquet on the PVC/object store.
3. **Verify** the copy (row counts + checksum).
4. Drop the partition.
5. Log what you did; confirm the size dropped.

### RO-04 — Rebuild a loan balance from events
1. Identify the drifted loan.
2. Reset its `outstanding` (to 0 or its opening balance).
3. Replay its events from the stream/archive through the idempotent consumer.
4. Confirm `outstanding` == sum of changes.
5. Find and fix the root cause of the drift.

### RO-05 — Back up and restore
1. Dump Postgres (and note the archive location).
2. Verify the dump restores into a scratch database.
3. Restore drill: on a schedule, not just when you need it.
4. Document the exact commands and where backups live.

### RO-06 — Full teardown and rebuild
1. `terraform destroy` in a scratch environment.
2. `terraform apply` from scratch.
3. Confirm the whole stack comes back (data layer, apps, edge, observability).
4. This is your reproducibility proof — run it before you trust the system.

---

## Adding a runbook

When you add an alert, add its runbook in the same change. If you can't write "first
thing to check," the alert isn't actionable yet — refine or remove it.
