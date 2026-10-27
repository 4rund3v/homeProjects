# 08 — Object Storage: S3-compatible with MinIO

**Folder:** `08-object-storage/`
**Milestone:** M3 (stateful foundations)

---

## Teach first: object storage vs. block vs. file

Storage comes in three shapes:

| Type | Model | Example |
|---|---|---|
| **Block** | Raw disk; you manage FS | EBS volume, LVM, a raw disk in Proxmox |
| **File** | Files on a shared FS | NFS, CephFS, an SMB share |
| **Object** | Named blobs in a bucket, addressed by HTTP | S3, GCS, Azure Blob, **MinIO** |

**Object storage** is designed for unstructured data (documents, images, backups, logs). It's:

- **HTTP-native.** Access via HTTPS; every operation is a REST call.
- **Scalable.** Petabytes per bucket, no filesystem limits.
- **Replicated.** Objects are stored across nodes with strong durability guarantees.
- **Expensive vs. block/file per-byte, but the API and scaling win for unstructured data.**

An object store is **not** a filesystem: no directory listings at the raw-API level (there are conventions), no renames, no partial updates — you upload a whole object, you read it whole.

---

## Why MinIO

For a homelab, **MinIO** is the standard self-hosted S3-compatible store. It speaks the S3 API, so any tool or library that uses S3 (aws-cli, boto3, Rclone, Harbor, CNPG backups, Outline's file storage) works unchanged — you just point the endpoint at MinIO.

Alternatives: Ceph (feature-rich, complex), Garage (Rust, minimalist), RustFS (newer). **MinIO is the pragmatic default** — battle-tested, well-integrated, active community.

---

## MinIO on Kubernetes

MinIO has two deployment shapes:

- **Standalone** — one container, one filesystem-backed volume. Fine for dev.
- **Distributed** — an **Erasure Code** deployment across N pods, each with its own volume. Requires `N ≥ 4` for strong durability; typical is 4 or 8.

> **What Erasure Coding actually is (the mechanism, not the slogan):** instead of *replicating* an object (store the whole thing K times), EC **shards** it into `D` data chunks + `M` parity chunks and scatters all `D+M` chunks across distinct pods/drives — `EC:2` means `D=2, M=2`, so 4 chunks total, 4 pods. The math that makes it work: **you can reconstruct the object from *any* `D` of the `D+M` chunks** (this is Reed–Solomon coding, the same algebra as an error-correcting code / a QR code). So with `EC:2` you need any 2 of the 4 chunks to read a write **or** to rebuild after loss — that's *why* "tolerates 2 failures" is the literal count, not a policy: lose 2 pods (2 of your 4 chunks) and you still have the other 2 = exactly `D`, the minimum reconstructable set. Lose a 3rd and you have fewer than `D` → unrecoverable. **Contrast with replication:** replication tolerates 1 failure per replica *only* and stores the full object N× (3× the bytes for 3 replicas); EC:2 stores only 2× the bytes and tolerates 2 failures *concurrently* — that's the whole reason to prefer it for large object stores.

> **Threshold — Erasure Coding.** Distributed MinIO uses EC to protect against drive failures. With 4 nodes and EC:2, the cluster tolerates 2 node failures while still able to read/write. With fewer than 4 pods you lose redundancy. **4 pods is the minimum sensible distributed deployment.** For a homelab, standalone is fine for Outline's uploads, but you want distributed if you're using MinIO for Postgres backups (where durability is non-negotiable).

### MinIO chart values

```yaml
# values.yaml
mode: standalone                       # or "distributed" with minio.podAntiAffinityPreset
buckets:
  - name: outline-files
    policy: none
  - name: pg-backups
    policy: none

persistence:
  enabled: true
  storageClass: ""                     # local PVs or NFS
  size: 100Gi

ingress:
  enabled: true
  ingressClassName: nginx
  hosts: [minio.lab.example]
  tls: true

auth:
  rootUser: minioadmin
  # rootPassword: use existingSecret (Pattern B from doc 03)
```

> **Tradeoff — local PVs vs. network storage for MinIO.** MinIO with **local PVs** on distinct nodes is the recommended production shape — it's what Erasure Coding is designed for (each node owns its own physical disk). Putting all pods on a shared NFS volume defeats the redundancy model: a NFS outage takes down the whole object store at once. **Use local PVs, one node per pod.**

---

## Access control: buckets, policies, service accounts

Object storage has its own IAM, independent of k8s RBAC:

- **Buckets** — top-level namespaces (`outline-files`, `pg-backups`, `harbor-images`).
- **Access keys** — long-lived credentials for machines (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`).
- **Policies** — what a key can do on which buckets (`PutObject` on `outline-files/*`, `GetObject` on `pg-backups/*`).
- **Console** — a web UI for humans to manage users/policies.

The k8s ServiceAccount ↔ MinIO access-key mapping matters:

```
k8s SA (outline:app)  →  MinIO access key (outline-app)  →  policy: rw on outline-files
k8s SA (cnp operator) →  MinIO access key (pg-backups)   →  policy: rw on pg-backups
```

> **Senior lens** — this mapping is where people go wrong. Either you hand every workload the same admin key (a huge blast radius), or you manage per-workload keys and rotate them. **Use External Secrets Operator** (doc 14) to inject each MinIO access key into its owning workload — one Secret per key, referenced by name in each Deployment. Rotating a key then means rotating one Secret; every workload picks it up on next restart.

---

## The Outline integration

Outline expects S3-compatible storage for attachments. In values:

```yaml
configMap:
  extra:
    STORAGE_URI: "s3://outline-files"
    STORAGE_BASE_URL: "https://minio.lab.example/outline-files"
    STORAGE_HOST: minio.storage.svc.cluster.local
    STORAGE_PORT: "9000"
    STORAGE_USE_SSL: "false"          # inside the cluster; external clients use https
    STORAGE_S3_FORCE_PATH_STYLE: "true"
```

S3 credentials go to the Secret (Pattern B):

```yaml
secrets:
  existingSecret: outline-secrets      # contains STORAGE_ACCESS_KEY_ID / STORAGE_SECRET_ACCESS_KEY
```

Now Outline reads/writes files to your MinIO bucket, and you control retention, backups, and access.

---

## Using MinIO for backups (the second job)

Once you've got it, MinIO becomes your backup target for everything:

- **CloudNativePG backups** (doc 06) → `pg-backups` bucket.
- **Velero** (doc 15, whole-cluster backup) → `velero-backups` bucket.
- **Harbor image storage** (doc 05) — optionally, if you want image retention on top of MinIO.
- **Log retention** (doc 12) — long-term archive.

**One object store, every durability layer.** This is a common pattern: pick a storage substrate that all your tooling can agree on.

> **Failure mode — using the same MinIO as both source and backup target.** If MinIO is your backup store and MinIO's node fails, backups and live data fail together. **Run MinIO on the same cluster but treat its own data with the same durability you'd give Postgres** — EC:2 across 4+ nodes, and consider a remote MinIO (or a cloud bucket) as the tier-2 backup target. This is doc 15's job.

---

## The workflow you'll live in

```
# CLI access
mc alias set lab https://minio.lab.example minioadmin <password>
mc mb lab/outline-files lab/pg-backups
mc admin user add lab outline-app <password>
mc admin policy attach lab readwrite bucket=outline-files user=outline-app
mc ls lab/outline-files
mc cp file.jpg lab/outline-files/

# Inside the cluster
kubectl exec -it minio-0 -- mc ls local
kubectl logs -n storage minio-0 -f
```

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| Standalone vs distributed | Standalone for low-stakes; distributed (≥4 pods) for anything that needs durability |
| Erasure code | EC:2 on 4 nodes = tolerates 2 failures |
| Storage backend | Local PVs, one per node — not a shared NFS |
| Access keys | Per-workload, injected via external secret (Pattern B) |
| Bucket layout | One per data domain (`outline-files`, `pg-backups`, `velero-backups`) |
| Retention | Lifecycle rules on archives; don't let backups age into a data lake |
| Same-store backup | Avoid; run a second MinIO or cloud bucket for tier-2 backups |

---

## Failure modes you must deliberately cause

1. **Kill a MinIO pod** (in a distributed setup) → confirm EC tolerates it; verify reads still work.
2. **Kill 2 pods at once** (with EC:2) → confirm at the boundary; understand where durability breaks.
3. **Attach a wrong policy** → observe a 403 in the app; learn the IAM surface.
4. **Rotate an access key without updating the Secret** → pods fail to upload; see the failure mode for un-rotated external secrets.
5. **Fill the PVCs** → understand the storage limit that governs the whole backup story.

---

## Exit criteria (MinIO part of M3)

- [ ] MinIO running with TLS, console access, ingress
- [ ] Buckets created per data domain (`outline-files`, `pg-backups`)
- [ ] Access keys per workload; injected via external secrets
- [ ] Outline uploads attachments to MinIO successfully
- [ ] CloudNativePG backups land in MinIO on schedule
- [ ] Policies deny cross-workload bucket access (verify with a wrong key)

Next: `09-oidc-auth-jwt` — authentication as a real system.
