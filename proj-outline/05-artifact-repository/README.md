# 05 — Harbor: The Artifact Repository

**Folder:** `05-artifact-repository/`
**Milestone:** M5 — Registry

---

## Teach first: what an artifact repository is and why registries matter

### The problem

Your CI builds a Docker image. Where does it live? If the answer is "nowhere, Jenkins just pushes to Docker Hub" you have three problems:

1. **Provenance.** You can't answer "what exactly is running in prod?" — the tag `:latest` on Docker Hub is a moving target.
2. **Availability.** Docker Hub rate-limits and goes down. Your deploy pipeline now depends on a third party's uptime.
3. **Security.** Anyone can push anything to a shared namespace; nothing scans images; no retention policy.

An **artifact repository** is the store of built things — container images, Helm charts (as OCI artifacts), sometimes Maven/npm packages. It's the bridge between CI (which produces) and CD (which consumes).

### What Harbor adds over a plain registry

A plain registry (registry:2) stores and serves images. **Harbor** is a registry *plus*:

- **Projects & RBAC** — namespaces with per-user/team permissions.
- **Vulnerability scanning** — Trivy integrated; every push gets a CVE report.
- **Image signing & trust** — cosign/Notary support; only signed images can be pulled (if you enforce it).
- **Retention rules** — "keep last 10 per repo, expire everything older than 30 days."
- **Replication** — pull-through cache of Docker Hub (fixes rate limits), replicate between registries.
- **Helm chart storage (OCI)** — charts and images live in one place.
- **Quotas & garbage collection** — bound disk usage.

> **Senior lens** — the scanning and retention features are what make Harbor *operational* rather than just a bucket. A registry without scanning ships CVEs silently; without retention, it fills the disk and every pull fails. Both are failure modes you'll deliberately cause later.

---

## Why this fits *this* project

The delivery chain you're building is:

```
Jenkins builds → Harbor stores (image + chart) → CD pulls from Harbor → cluster runs it
```

Harbor is the **contract point** between CI and CD. Both sides speak OCI, and the artifact in the middle is immutable and addressable by digest. That immutability is what makes rollback trivial and "what's running?" answerable.

Also, running Harbor yourself is *itself* a good exercise: it's a multi-component stateful app (registry, core API, jobservice, database, Redis, Trivy) with real operational weight.

---

## Harbor's own architecture (worth studying)

| Component | Role |
|---|---|
| **core** | API server, config, RBAC |
| **registry** | the actual OCI distribution server (upstream docker distribution) |
| **jobservice** | async jobs — scanning, replication, GC |
| **database** | Postgres — Harbor's metadata (projects, users, policies) |
| **redis** | job queue state |
| **trivy** | the vulnerability scanner |
| **nginx (portal)** | front door, routes to core/registry/portal |

Harbor is itself a stateful multi-tier app on Postgres + Redis + PVCs. Sound familiar? It's the same shape as Outline. Running it via Helm teaches you nothing new about *writing* charts, but a lot about *operating* one that matters.

> **Threshold — Harbor's database is not your application database.** Harbor bundles its own Postgres. Resist the urge to "share" the CloudNativePG cluster with it at first; keep Harbor self-contained so a Postgres maintenance window doesn't take out your delivery pipeline. Revisit after doc 15.

---

## Image tagging strategy

This is a policy decision you must make explicitly:

| Tag | Meaning | Use |
|---|---|---|
| `:latest` | whatever was built last | **never for deploys** |
| `:<git-sha>` | exact commit | **the deploy unit** — immutable, traceable |
| `:<semver>` (v1.4.2) | tagged release | stable pointer for humans |
| `:<branch>` | branch tip | dev convenience only |

> **Senior lens** — deploy by git SHA, always. The SHA answers "what code is running?" and gives you an exact rollback target. Semver tags are for humans to read; digests (`image@sha256:...`) are the truly immutable identity. In CD, pin by digest when you can; by immutable tag otherwise.

---

## Scanning as a gate

Trivy scans each pushed image for OS + language CVEs. The policy question: **what blocks a deploy?**

- `NONE`/`LOW` — pass.
- `MEDIUM` — warn.
- `HIGH` — warn or block (your call).
- `CRITICAL` — **block**.

> **Tradeoff — strictness vs. velocity.** Blocking on HIGH means you stop shipping over CVEs with no exploit path in your context (a lib used only at build time, e.g.). Not blocking means you accumulate risk silently. A pragmatic senior-level policy: **block CRITICAL, track HIGH as debt with an SLA** (fix within N days), and use Harbor's project-level "prevent vulnerable images from running" only in prod projects. This is a real tradeoff, not a checkbox.

---

## Retention

Without a policy, every push lives forever. On a homelab disk, that's fatal.

Example policy: *keep the 10 most recent images per repo, and anything tagged `v*`.*

> **Failure mode — garbage collection.** Deleting a tag in Harbor marks layers deletable but doesn't free disk until GC runs (it stops the registry, rewrites the storage, restarts — Harbor 2.x has online GC, still heavy). If your disk fills before GC, pulls fail cluster-wide. **Monitor registry disk usage and alert before 80%.**

---

## Pull-through cache (proxy cache)

Configure a proxy project for `docker.io`. Your nodes pull base images through Harbor; Harbor caches them. This eliminates Docker Hub rate limits and pins a known-good copy of `ubuntu:22.04` inside your lab.

> **Senior lens** — a proxy cache is also a *supply-chain* control: you can later audit exactly which base images your cluster has ever pulled, and block direct pulls from the internet. This is the beginnings of an admission policy (doc 14).

---

## The workflow you'll live in

```
docker login harbor.lab.example
docker build -t harbor.lab.example/outline/outline:<sha> .
docker push harbor.lab.example/outline/outline:<sha>

helm push outline-0.1.0.tgz oci://harbor.lab.example/chartrepo/outline
helm upgrade --install outline oci://harbor.lab.example/chartrepo/outline --version 0.1.0
```

In the cluster, a pull secret (`imagePullSecrets`) authorizes pulls — created by Jenkins from its credentials, scoped to the project.

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| Block on scan | CRITICAL blocks; HIGH tracked as debt |
| Tagging | SHA for deploys, semver for humans, `:latest` never |
| Retention | Last 10 + tagged releases; alert at 80% disk |
| GC | Schedule off-peak; verify disk actually frees |
| Proxy cache | Configure for docker.io day one |
| Self-host vs managed | Self-host here to own the chain; know the ops cost |

---

## Failure modes you must deliberately cause

1. **Fill the disk** → watch pulls fail cluster-wide; learn why disk alerts must fire at 80%.
2. **Delete a tag** → see storage not freed until GC; run GC.
3. **Deploy an image with a CRITICAL CVE** → watch the gate hold (if enforced).
4. **Let a retention rule expire an image that's still deployed** → `ImagePullBackOff` on rollback; learn to retain the running version.
5. **Revoke the pull secret** → confirm pods can't start; understand the auth path.
6. **Restart Harbor entirely** → the pipeline should survive (images cached on nodes); note what actually breaks.

---

## Exit criteria for M5

- [ ] Harbor running via Helm with TLS, its own Postgres/Redis/PVCs
- [ ] A project per app (`outline/`), with robot accounts for CI push and cluster pull
- [ ] Trivy scanning on push; CRITICAL blocks deploys in the pipeline
- [ ] Retention policy active; disk usage alerted at 80%
- [ ] Proxy cache for docker.io configured
- [ ] Charts stored as OCI artifacts alongside images

Next: `06-postgres-stateful` — the database under everything.
