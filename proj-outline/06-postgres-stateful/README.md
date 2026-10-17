# 06 — Postgres: The Stateful Heart

**Folder:** `06-postgres-stateful/`
**Milestone:** M3 (stateful foundations)

---

## Teach first: what makes a database *stateful*

In Kubernetes, "stateful" means: **the pod has data that must survive the pod's death and rescheduling.** For Postgres, that data is the database files on disk.

This creates a set of constraints a plain Deployment can't satisfy:

1. **Stable identity.** The pod must be able to find its data after a restart. Deployment pods get random names (`app-7d9f-abc`); if pod #2's data is on disk and pod #3 spawns, pod #3 must attach to the same disk.
2. **Single-writer storage.** A database can't have two pods writing to the same file. The storage must be `ReadWriteOnce`.
3. **Ordered identity.** If you run replicas (primary + standby), peers must address each other by name (`postgres-0`, `postgres-1`), not by random hash.

**StatefulSet** is the k8s primitive that gives you exactly these three things. Everything else is derived from them.

---

## The StatefulSet contract

```yaml
apiVersion: apps/v1
kind: StatefulSet
spec:
  serviceName: postgres           # headless Service — DNS by ordinal
  replicas: 3
  selector:
    matchLabels: { app: postgres }
  template:
    spec:
      containers:
      - name: postgres
        ports: [{ containerPort: 5432 }]
        volumeMounts:
        - name: data
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: [ReadWriteOnce]
      resources: { requests: { storage: 50Gi } }
```

The magic is `volumeClaimTemplates`. For each replica, k8s creates a **distinct PVC** and mounts it at that pod's path. Pod `postgres-0` owns `data-postgres-0`; `postgres-1` owns `data-postgres-1`. **Delete `postgres-1` and it comes back attached to `data-postgres-1` — its data is intact.**

Compare a Deployment: `volumeClaimTemplates` doesn't exist. If you want per-pod storage, you hand-roll PVCs and wire them by pod index — painful and brittle.

---

## The headless Service — how peers find each other

Every StatefulSet needs a **headless Service** (`clusterIP: None`). Instead of load-balancing across pods, it publishes **stable DNS entries per ordinal**:

```
postgres-0.postgres.database.svc.cluster.local   → postgres-0's IP
postgres-1.postgres.database.svc.cluster.local   → postgres-1's IP
postgres-2.postgres.database.svc.cluster.local   → postgres-2's IP
postgres.database.svc.cluster.local              → all pods (for clients)
```

This is how a standby knows its primary's address, and how a k8s service can address all replicas for client traffic.

> **Senior lens** — a headless Service is not optional for StatefulSets with more than one replica. Skip it and inter-pod addressing breaks; you'll see confusing "connection refused" errors from within the cluster that no amount of firewall debugging will fix.

---

## CloudNativePG: the operator pattern

Running a raw StatefulSet + `postgres` container is fine for learning, but it's *not* how you run Postgres in production. A database needs:

- Failover between replicas
- Automated backups and restores
- Schema migrations / role management
- SSL/TLS for connections
- Connection pooling
- Monitoring that a human can interpret

**CloudNativePG** (CNPG) is a Kubernetes operator that manages all of this. An **operator** is a controller that watches for a *custom resource* (in this case, a `Postgresql` CRD) and reconciles the actual Postgres cluster (StatefulSets, ConfigMaps, backups, failover) to match it.

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Postgresql
metadata:
  name: outline
spec:
  instances: 3
  imageName: postgres:16
  primaryUpdateStrategy: unsupervised
  storage:
    size: 50Gi
  backup:
    barmanObjectStore:
      destinationPath: s3://pg-backups/outline
      configuration: { awsEndpoint: http://minio.storage:9000 }
  cronJob:
    - schedule: "0 3 * * *"
      postgresql: "SELECT pg_start_backup()"
```

You declare *what Postgres you want* (`instances: 3`, `backup: ...`). CNPG creates the StatefulSet, headless Service, ConfigMap, Secrets, backup Jobs — and does the failover when `postgres-0` dies.

> **Tradeoff — raw StatefulSet vs. operator.** A raw StatefulSet is one less moving part, teaches you the primitives, and is honest about how much work real ops involves. An operator hides that work but adds its own failure modes (operator bugs, CRD version skew, controller panics). **For learning, do the raw StatefulSet first, then install CNPG and re-deploy the same database.** The contrast is where the intuition forms. For real work, use an operator — nobody runs raw Postgres on k8s in production.

---

## PVC sizing — the number nobody gets right

PVCs don't grow automatically (unless you enable volume expansion, and only for certain storage classes). Once a PVC's storage fills, **writes fail** and the database is dead.

| Kind of data | Size guidance |
|---|---|
| Small tool (Harbor DB) | 5-10 GiB + generous headroom |
| Outline DB (docs + attachments metadata) | 20-50 GiB; watch growth |
| Production Postgres | Size from growth rate × retention, plus 2× headroom |

> **Threshold — Postgres needs ~2× its data size in free disk** for normal operation (WAL, temp files, autovacuum, vacuum workspaces). A PVC that's 90% full is on the edge of a fatal failure, not merely "running out." Alert at 80%; page at 90%.

### Enabling expansion

Some StorageClasses support online volume expansion (`allowVolumeExpansion: true`). With it, `kubectl edit pvc` can grow the PVC without downtime. On a homelab with local storage or NFS this often works; on plain LVM it may not. **Verify your StorageClass supports it before assuming you can grow later.**

---

## Connection pooling — the pattern people skip

Every app connects to Postgres. With Outline's API server at `replicaCount: 4`, plus workers, plus backups, plus a migration Job, that's dozens of simultaneous connections. Postgres's default `max_connections` is 100, and *each connection eats ~10MB of memory* — so at 100 connections you've burned a gigabyte just on connection state.

**PgBouncer** sits in front of Postgres and pools connections: the app opens many cheap connections to PgBouncer, PgBouncer maintains a small set of real Postgres connections.

```
app (50 conns) → PgBouncer (pool of 20) → Postgres
```

> **Tradeoff — transaction pooling vs. session pooling.** Transaction pooling closes the real connection after each transaction; the app cannot use session state (prepared statements, LISTEN/NOTIFY, advisory locks that persist across transactions). Outline and many apps *need* session pooling. Choose based on what your app requires, not the default.

---

## Backups — three distinct strategies

| Method | What | When |
|---|---|---|
| **Continuous WAL archiving** | Every transaction log shipped to object storage | Baseline; enables PITR |
| **Base backup** | A full snapshot taken on a schedule | Recovery anchor |
| **Point-in-time restore (PITR)** | Replay WAL to any second | When you need "undo my mistake" |

CNPG does this for you via Barman, with backups landing in your MinIO bucket (doc 08).

> **Threshold — never test your backup.** An untested backup is not a backup. Every so often, run a restore into a throwaway cluster and verify data. **Time your first restore before you need it**, because the second time you restore is the one that matters.

---

## The workflow you'll live in

```
kubectl exec -it outline-pg-0 -- psql -U outline
kubectl exec -it outline-pg-0 -- psql -U postgres -c "SELECT * FROM pg_stat_activity;"
kubectl logs outline-pg-0
kubectl get pgoutline outline
kubectl cpg failover outline            # force failover (CNPG CLI)
kubectl cpg backup outline backup-2024
kubectl cpg restore outline --target-time "2024-01-15 03:00:00Z"
```

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| replicas | 3 minimum (quorum for primary election) |
| Disk alert | 80% page, 90% critical (2× data headroom needed) |
| StorageClass | Must support RWX? No. Support expansion? Verify. |
| Operator | CNPG for real work; raw StatefulSet for learning |
| Pooling | PgBouncer in front; transaction or session mode per app |
| Backups | Base + WAL archiving; test restores regularly |
| Retention | Base backups: days; WALs: hours |

---

## Failure modes you must deliberately cause

1. **Fill the PVC** → observe Postgres refusing writes; learn the alert threshold.
2. **Kill the primary** (`kubectl delete pod outline-pg-0`) → CNPG promotes a standby; measure failover time.
3. **Force a failover** with CNPG CLI → confirm the app reconnects; note the brief write outage.
4. **Delete a PVC (with Retain)** → confirm the data is preserved, not deleted.
5. **Delete a PVC (with Delete)** → do this in a test database; feel what you'd lose in prod.
6. **Run a restore to a point in time** → this is the drill. Do it. Do it again.

---

## Exit criteria for M3 (Postgres)

- [ ] CloudNativePG Postgres cluster running with 3 instances
- [ ] PVCs provisioned per replica; app connects and can write
- [ ] Automatic failover verified (kill primary, watch promote)
- [ ] Continuous backup to MinIO; a PITR drill has succeeded
- [ ] PgBouncer in front; connection count is bounded
- [ ] Disk alert wired to 80% / 90%

Next: `07-redis-queue` — the cache and job queue.
