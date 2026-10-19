# 15 — Backup and Disaster Recovery

**Folder:** `15-backup-dr/`
**Milestone:** M14 — Backup/DR

---

## Teach first: RPO and RPO's twin, RTO

Two numbers define every backup strategy. Everything else is implementation:

- **RPO — Recovery Point Objective.** *How much data can you afford to lose?* Measured in time: RPO of 1 hour means a disaster at 12:00 loses everything since 11:00.
- **RTO — Recovery Time Objective.** *How long can the service be down?* Measured in time to restore.

These are **business decisions**, not technical ones. For a homelab knowledge base:

| Scenario | Sensible RPO | Sensible RTO |
|---|---|---|
| "I'd be annoyed to lose a doc" | 24h | 1 day |
| "My team's notes live here" | 1h | 4h |
| "This is production practice" | 15min | 1h |

> **Senior lens — RPO is determined by backup *frequency*; RTO by backup *quality* (tested restore speed).** People obsess over frequency and never test restores — so their real RPO is fine but their real RTO is *unknown*, which means infinite. An untested backup is a hope, not a plan. This doc's exit criteria are mostly restore drills for exactly that reason.

---

## What you actually need to back up (the inventory)

Walk the stack from doc 01 down and classify everything:

| Thing | State? | Backup method | RPO driver |
|---|---|---|---|
| **Terraform code, charts, Jenkinsfiles** | in Git | Git remote (offsite: GitHub) | n/a |
| **Container images** | rebuildable | Harbor (+ proxy cache) | n/a — rebuild from Git |
| **Postgres data** | **critical** | CNPG WAL archiving + base backups → MinIO | minutes (WAL is continuous) |
| **MinIO objects (attachments)** | **critical** | MinIO replication or `mc mirror` to second store | hours |
| **Redis** | transient | **don't back up** (rebuild from Postgres) | n/a |
| **k8s cluster state** | derivable | Terraform + Helm — *that's the point of docs 01–03* | n/a |
| **k8s Secrets** | painful-to-regenerate | Sealed Secrets in Git, or export encrypted | hours |
| **Keycloak realm/users** | **critical** (it's Postgres) | its own PG backup | minutes |
| **Grafana dashboards, Prometheus rules** | in Git ideally | export as code (grafana-sdk / Jsonnet / `grafctl`) | n/a |
| **Jenkins job config** | JCasC in Git | Git | n/a |
| **Harbor metadata** | medium | Harbor's chart backs up its PG; or accept re-push | hours |

> **Senior lens — the class system.** Every byte in the cluster is one of: **(a) in Git, (b) derivable from Git + images, (c) real user data.** Only (c) needs traditional backup. The discipline of pushing everything into (a)/(b) — which docs 01–04 built — is what keeps this table short. A cluster where you can't tell which class a thing is in is a cluster you can't recover.

---

## Postgres backup: WAL archiving + base backups (CNPG)

Already wired in doc 06; here's what's actually happening:

```
outline writes → WAL segments (16MB files, continuous) ──archive──▶ MinIO pg-backups
                        ▲
                        └── base backup (daily, full snapshot) ──▶ MinIO pg-backups
```

- **Base backup** = consistent full copy. Recovery anchor.
- **WAL archive** = every transaction since. **This is what gives you point-in-time recovery (PITR)** — "restore to 14:32:05, right before the DROP TABLE."
- CNPG also keeps 2 on-cluster replicas (doc 06) — but replicas protect against *node* failure, not *logical* error. A `DELETE WHERE id IS NOT NULL` replicates happily to all replicas. **Replication is not backup.** Only PITR saves you from yourself.

Retention: base backups for N days (14 is generous), WALs to match. CNPG's `barmanObjectStore` retention policy governs both.

### The restore drill (the only part that matters)

```
# 1. Spin up a restore-target cluster in a scratch namespace
kubectl apply -f - <<EOF
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: outline-restore-test
  namespace: db-restore
spec:
  instances: 1                      # minimal — it's a drill
  storage: { size: 20Gi }
  bootstrap:
    recovery:
      source: outline-backup
      recoveryTarget:
        targetTime: "2026-10-15 14:32:05+00"    # the PITR moment
EOF

# 2. Wait for recovery; verify
kubectl -n db-restore exec outline-restore-test-1 -- psql -U outline -c "SELECT count(*) FROM documents;"

# 3. Tear it down
kubectl -n db-restore delete cluster outline-restore-test
```

Time the whole thing. **That number — minutes from "disaster declared" to "data verified" — is your real RTO for data.** Do it monthly; record the duration trend.

---

## Velero: cluster-level backup (and what it's for)

**Velero** snapshots k8s API objects (Deployments, Services, ConfigMaps, Secrets, CRDs) + (optionally) PV data, to object storage:

```
velero backup create daily-cluster --include-namespaces outline,database,identity,cicd --schedule "@every 24h"
```

What Velero is genuinely good for in *this* architecture:

- **PVCs you didn't otherwise cover** (Jenkins job history, Harbor's PG if you didn't put it on CNPG).
- **Cluster-object portability** — restore namespaces into a *rebuilt* cluster (the doc 01 destroy-and-rebuild drill, but keeping state).
- **Namespace-level undo** — "restore namespace X as it was yesterday."

What Velero is **not** for: replacing Postgres WAL backup. A PV snapshot of a running Postgres is *crash-consistent* (like pulling the power cord) — usually recoverable, occasionally not, never PITR-capable. **Layer it: Velero for cluster objects + PVCs; CNPG WAL for the databases.**

> **Tradeoff — Velero's snapshot story depends on storage.** On cloud, it uses native volume snapshots. On bare-metal homelab (local PVs, no CSI snapshot support), you're on `restic`-style file-copy backups (now "uploader" in newer Velero) — slower, and consistency depends on the app quiescing. Test what you actually have. If Velero fights your storage layer, the fallback is: cluster objects via `kubectl get all -o yaml` (or GitOps, docs 01–03) + data via per-service backups. **Don't keep a backup tool you've never restored with.**

---

## MinIO backup: the backup's backup

Your backups live *in* MinIO (docs 06, 12, Velero). MinIO is now the most important thing in the cluster.

Two layers:

1. **MinIO's own durability** — distributed mode with EC:2 across 4+ nodes (doc 08) survives node/disk loss.
2. **Tier-2: a copy off the cluster.** Options:
   - `mc mirror --watch` to another MinIO instance (a VM outside the cluster) or to real S3/B2 (cheap, offsite).
   - Scheduled `mc mirror` (cronJob) if continuous is overkill.

> **Threshold — the blast-radius rule.** Backups on the same physical host, same power strip, or same failure domain as production are not backups; they're copies that die together. Minimum viable offsite for a homelab: sync to a cloud bucket (Backblaze B2 ~$6/TB/mo) or a drive you physically rotate. If your threat model includes the house burning down, only offsite counts.

---

## The disaster scenarios (rehearse each once)

| # | Scenario | Recovery path | What it proves |
|---|---|---|---|
| 1 | **Deleted data** (bad migration, fat-fingered DELETE) | CNPG PITR to the second before | WAL archiving works |
| 2 | **Lost node** | k8s reschedules; PVs reattach (Retain policy, doc 02) | Platform resilience |
| 3 | **Lost whole cluster** (etcd dead, upgrade gone wrong) | Terraform rebuild (doc 01) + Helm re-deploy + CNPG restore from MinIO | Everything-as-code pays off |
| 4 | **Lost MinIO** | Rebuild MinIO; restore buckets from tier-2 mirror | The backup-of-backups works |
| 5 | **Full site loss** (homelab worst case) | Cloud tier-2 + Git remotes → rebuild anywhere | Offsite strategy works |
| 6 | **Ransomware/compromise** | Wipe, rotate *all* secrets (doc 14 inventory), rebuild from Git + known-good backups | You can act without paying |

Scenario 3 is the capstone — the doc 01 exit criterion ("rebuild from Git in under an hour") plus data restore. **Every scenario above should end with a written runbook entry in `16-operations-runbook`** — the drill's output is the document.

> **Failure mode — backups that pass until tested.** The classics: WAL archiving silently broken for 3 weeks (check `pg_stat_archiver`, alert on archive lag); restore cluster can't reach the backup bucket (NetworkPolicy, doc 14 — your hardening broke your recovery path); encrypted backups with a lost key; restore tested only by "it started," never verified with actual data queries. Each of these is found only by drilling.

---

## Monitoring the backup system itself

A backup pipeline is a production system — monitor it like one (doc 11):

```promql
# CNPG: is archiving falling behind?
time() - pg_stat_archiver_last_archived_time > 300

# Velero: last successful backup age
time() - velero_backup_last_successful_timestamp > 86400

# MinIO mirror: object counts diverging (simple canary)
minio_bucket_objects{bucket="pg-backups"} - mirror_bucket_objects{bucket="pg-backups"}
```

**Alert when backups *stop*, not when you need them.** "Last successful backup > N hours" is a page, always.

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| RPO | Set it *consciously*; WAL archiving gives ~minutes for near-zero effort |
| Postgres | CNPG base+WAL (PITR); never rely on replicas or Velero snapshots alone |
| Cluster objects | Git (Terraform/Helm) is the primary; Velero is the safety net + PVC catcher |
| Backups location | Different failure domain than prod; offsite tier-2 mandatory for real DR |
| Redis | Don't back up; rebuild |
| Drills | PITR monthly, full-cluster-rebuild quarterly; time them |
| Encryption | Encrypt tier-2 backups; keys stored *outside* the backup (Git- sealed or paper safe) |

---

## Failure modes you must deliberately cause

1. **DROP TABLE on production** → PITR to the second before; measure data loss (should be ~0).
2. **Break WAL archiving** (revoke bucket creds) → watch the alert fire; appreciate that you'd otherwise find out during the next disaster.
3. **`velero restore` into a fresh namespace** → verify objects come back *and work* (endpoints populate, pods run).
4. **Delete MinIO's PVCs** → rebuild from tier-2 mirror; time it.
5. **Full cluster rebuild drill** (scenario 3): destroy, rebuild from Git, restore data. Under 4 hours first try is good; document every manual kick you needed — each one is a gap in docs 01–03.
6. **Try restoring with NetworkPolicies on** → watch recovery fail to reach the bucket; add the recovery path to the allow-lists.

---

## Exit criteria for M14

- [ ] RPO/RTO written down per data class — even for a homelab, *decided*, not defaulted
- [ ] CNPG: base backups + WAL archiving to MinIO; archive-lag alert firing in a drill
- [ ] PITR restore drill done, timed, verified with data queries — monthly cadence set
- [ ] MinIO tier-2 mirror exists off-cluster; restore-from-mirror tested
- [ ] Velero (or documented equivalent) backing up cluster objects + orphaned PVCs; one restore verified
- [ ] All six disaster scenarios rehearsed at least once; runbook entries written (→ doc 16)
- [ ] "Last successful backup" alerting live for every backup job

Next: `16-operations-runbook` — the day-2 habits that hold it all together.
