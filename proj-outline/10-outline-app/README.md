# 10 — The Outline Application: Architecture and Deployment

**Folder:** `10-outline-app/`
**Milestone:** M8 (Outline live), M9 (workers)

---

## Teach first: reading an application before deploying it

The platform work (docs 01-09) is the same regardless of payload. This doc is where you **read a real application** and translate its architecture into Kubernetes resources. This is a skill distinct from platform skills: given an unfamiliar app, extract its deployment topology from its docs and source.

The checklist for any app:

1. **Processes** — does it run one process type or several (API, workers, cron)?
2. **Dependencies** — databases, caches, object stores, external APIs. Which are required vs. optional?
3. **Configuration surface** — env vars, config files. What's sensitive?
4. **State** — what data does it own? Where does it write?
5. **Health endpoints** — how do we know it's alive vs. ready?
6. **Scaling model** — which processes scale horizontally? Which are singletons (cron leader)?
7. **Build** — how is it packaged (runtime, bundler, migrations)?

You'll apply this to Outline, and it generalizes to every app you'll ever deploy.

---

## Outline's architecture

Outline is a Node.js/TypeScript app (React frontend, Express-ish server API, Postgres via Sequelize, Redis for cache/queues).

The critical fact: **Outline has (at least) two process types.**

| Process | Job | Scaling |
|---|---|---|
| **Server (`node build/server/index.js`)** | Serves the web UI + HTTP API; accepts connections; runs the WebSocket/realtime collaboration | Horizontal — stateless behind a Service |
| **Worker (`node build/worker/index.js`)** | Processes background jobs: email, search indexing, imports/exports, webhooks, cleanup tasks | Horizontal — competes for Redis-backed queues |
| **Cron / scheduled tasks** | Maintenance (expiring old data, cleanup) | Singleton — must run on exactly one instance (Outline runs these inside the server process; the pattern matters more than the detail) |

> **Senior lens** — this two-process shape (web + worker) is *the* standard 12-factor deployment topology. Once you see it, you see it everywhere: GitLab (puma + sidekiq), Sentry (web + workers), Mastodon (web + sidekiq), Discourse. The reason it exists: web processes must stay responsive (fast timeouts, horizontal scale), while jobs are slow (minutes, retries, backpressure). Mixing them means one long import blocks an HTTP request. **Separate Deployment per process type, always** — you can't independently scale or deploy them otherwise.

In Kubernetes terms:

```
Deployment: outline-server     (replicas: 2+, env: SERVE=1)
Deployment: outline-worker     (replicas: 2, different command)
```

Both share the same image and the same env (DB/Redis/S3/OIDC config); they differ in `command:`.

---

## Dependencies (from Outline's own docs/source)

| Dependency | Required? | Kubernetes home |
|---|---|---|
| PostgreSQL | **Required** | CloudNativePG (doc 06) |
| Redis | **Required** (queues, cache, collaboration) | Bitnami chart (doc 07) |
| S3-compatible storage | **Required** for attachments | MinIO (doc 08) |
| OIDC provider | Required for login | Keycloak (doc 09) |
| SMTP (email) | Optional (invites, notifications) | Optional in-cluster SMTP or disabled |
| Slack/Discord/Google integrations | Optional | disabled by default |

> **Failure mode — the "optional" dependencies that aren't.** Outline technically boots without SMTP, but passwordless flows and invites silently fail. Read the app's actual behavior, not just its README. The general lesson: distinguish *boots* from *fully functional*. Probes (below) tell you the process is up; only exercising user flows tells you the app works.

---

## Configuration surface

Outline is configured almost entirely via env vars. The values-vs-configmap doc (`03-helm-packaging/values-vs-configmap.md`) applies directly here. The shape we settled on:

**Explicit (ConfigMap):**
```
PUBLIC_URL, SERVER_URL, HOSTNAME, PORT
DATABASE_URL (non-secret parts), REDIS_URL (non-secret parts)
STORAGE_* (bucket, endpoint, region, force-path-style)
OIDC provider discovery URL, client id
```

**Secret (Pattern B — existing Secret):**
```
SECRET_KEY, APP_SECRET  (session/encryption keys)
DATABASE_URL password, REDIS password
OIDC client secret
S3 access key + secret
UTILS_SECRET
```

**Open map (ConfigMap extra):** everything else — `LOG_LEVEL`, `MAXIMUM_UPLOAD_SIZE`, `DEFAULT_LANGUAGE`, feature flags, `DEBUG` categories.

> **Threshold — `SECRET_KEY`/`UTILS_SECRET` rotation.** These encrypt sessions and signed URLs. Rotating them invalidates every active session (users get logged out) and can break old signed URLs — annoying but safe. Losing them entirely can mean unreadable encrypted columns. **Generate once, store in the secret manager, back it up with the database (doc 15). Never regenerate casually.**

---

## Migrations

Outline runs SQL migrations (Sequelize) at server startup — `sequelize db:migrate` is embedded in the boot path when deployed.

This creates a deploy-ordering concern:

- If 2 server pods + 2 worker pods start "simultaneously" on upgrade, **two processes may run migrations concurrently**.
- Most migration runners take an advisory lock (`pg_advisory_lock`) making concurrent runs safe-but-serialized; but a long migration means the second process waits, and readiness probes may time out.

> **Senior lens** — the three standard strategies:
> 1. **Migrate at boot (Outline's default).** Simple, works for small scale. Risk: slow migrations hold up rollouts; concurrent boots contend.
> 2. **Explicit migration Job before deploy** (helm pre-upgrade hook or CD step). Observability is better — the pipeline stage says "Migrations: passed" and the new pods start against a migrated schema. **This is where you should graduate to (see doc 04, hooks discussion).**
> 3. **Expand-contract (backward-compatible migrations).** The production-grade answer for zero-downtime: N and N+1 app versions both work against the intermediate schema. Requires app discipline; out of scope for a homelab but know the term.
>
> During a rolling update, old pods (old schema expectations) and new pods (new schema) overlap. Expand-contract is what makes that safe; for a homelab, accept a brief "migrate then roll" window.

---

## Health probes

Map the app's endpoints to Kubernetes probes:

| Probe | Outline endpoint | Meaning |
|---|---|---|
| **liveness** | `/_health` (or a cheap process check) | "The process isn't deadlocked" — failure ⇒ restart pod |
| **readiness** | same or `/` with DB check | "I can serve traffic" — failure ⇒ remove from Service endpoints |
| **startup** | same as liveness with higher `failureThreshold` | "Migrations are still running, don't kill me yet" |

> **Tradeoff — what should readiness actually check?** If readiness checks DB connectivity, a DB blip removes *all* server pods from the Service — you turned a partial outage into a total one (empty endpoints, 503s for everyone). If it checks nothing but the process, you route traffic to pods that error on every request. **The senior answer: readiness checks "can I serve *most* requests" — process up + event loop responsive; liveness checks "am I wedged"; neither should create correlated failure.** Check DB in readiness only if the app genuinely cannot serve anything without it — and Outline without DB serves error pages, which is still better than nothing.

> **Threshold — probe tuning defaults.** `initialDelaySeconds` must exceed worst-case migration/startup time or you enter a crash-restart loop on every deploy. Use a **startup probe** (`periodSeconds: 10, failureThreshold: 30` = 5 min budget) instead of a giant liveness delay — that's exactly what startup probes exist for. Liveness `periodSeconds: 10`, `failureThreshold: 3` (30s to detect a wedge). Readiness faster: `periodSeconds: 5`, `failureThreshold: 3`.

---

## Resource sizing (starting points)

Observed-shape estimates for a small team (tune from `kubectl top` + Prometheus after M10):

| Process | requests | limits | Notes |
|---|---|---|---|
| outline-server | 250m / 512Mi | 1 / 1Gi | Node processes are memory-hungry; watch RSS |
| outline-worker | 250m / 512Mi | 1 / 1Gi | Spiky during imports/exports |

> **Tradeoff — one image, two Deployments.** Both process types ship in one image (same code, different command). Alternative: separate images per process. One image keeps versions lockstep (server and worker *must* be the same version — they share queue message formats) at the cost of a bigger image pulled by both. **Lockstep matters more than image size: use one image.** This "shared artifact, distinct commands" pattern is the same one you'd use for a Django+Celery app.

---

## The deployment topology, assembled

```
                     ┌────────────────────────────┐
   Users ── HTTPS ──▶│ ingress-nginx (+TLS)       │
                     └──────────┬─────────────────┘
                                │ host: outline.lab.example
                     ┌──────────▼─────────────────┐
                     │ Service: outline-server    │
                     └──────────┬─────────────────┘
              ┌─────────────────┼─────────────────┐
        ┌─────▼─────┐     ┌─────▼─────┐     ┌─────▼─────┐
        │ server-0  │     │ server-1  │     │ (HPA...)  │
        └──┬─┬─┬────┘     └───────────┘     └───────────┘
           │ │ │
   ┌───────┘ │ └────────────────┐
   │         ▼                  ▼
   │   ┌────────────┐    ┌────────────┐
   │   │ worker-0/1 │    │  Keycloak  │ (OIDC login redirects)
   │   └──────┬─────┘    └────────────┘
   ▼          ▼
┌──────────┐ ┌────────┐ ┌────────┐
│ Postgres │ │ Redis  │ │ MinIO  │  ← all StatefulSets, docs 06-08
└──────────┘ └────────┘ └────────┘
```

Everything on this diagram is now something you built in docs 01-09. This doc is the assembly step.

---

## Deploying workers safely

Workers consume queues. Two operational rules:

1. **Deploy workers *before* server on app upgrades** (or accept queued-job schema skew — usually fine for a homelab since jobs are small and versioned).
2. **Bound concurrency** — worker parallelism should be explicit (env var), because unbounded concurrency × big import = OOM. Set worker concurrency to something the resource limits can absorb.

> **Failure mode — poison messages.** One malformed job retried forever blocks the queue (or burns CPU in a retry loop). Bull/BullMQ-style queues use exponential backoff + max attempts, then move to a dead-letter set. Know where Outline's dead jobs go and check it during incident debugging — "the worker is idle but the queue is full" is almost always a poison message or an exhausted max-attempts situation.

---

## The workflow you'll live in

```
kubectl -n outline get pods                  # server + worker deployments
kubectl -n outline logs deploy/outline-server -f
kubectl -n outline logs deploy/outline-worker -f   # watch jobs process
kubectl -n outline exec -it deploy/outline-server -- sh
kubectl -n outline top pods
kubectl -n outline rollout status deploy/outline-server
kubectl -n outline rollout restart deploy/outline-worker
redis-cli llen outline:jobs                  # queue depth (via doc 07)
```

---

## Failure modes you must deliberately cause

1. **Scale server to 0** → ingress returns 503; Service endpoints empty. Verify your error page/timeout behavior.
2. **Scale worker to 0** → server keeps working, but emails/exports hang; queue depth grows. **Watch the queue depth metric climb — this is a dashboard you'll build in doc 11.**
3. **Kill Postgres** → server 500s, readiness flaps, pods stay alive (liveness shouldn't restart them — restarting doesn't fix the DB). Confirm your probe design.
4. **Wrong `SECRET_KEY` after a "rebuild everything" drill** → sessions invalid, possibly encrypted data unreadable. Understand what each secret protects.
5. **Run two migration-booting pods concurrently** → observe the advisory-lock serialization (or contention) during rollout.
6. **OOM-kill a worker mid-import** → see retries resume the job; verify idempotency assumptions.

---

## Exit criteria for M8 & M9

- [ ] Two Deployments (server, worker) from one image, sharing config via ConfigMap + Secret
- [ ] Ingress + TLS working; login via Keycloak succeeds
- [ ] A document with an attachment can be created (proves Postgres + MinIO + OIDC + server all work)
- [ ] Background job observed processing (email/export/webhook) — worker logs show it
- [ ] Probes: startup (migration-safe), liveness, readiness — each failure simulated once
- [ ] HPA on server; queue-depth-aware scaling understood (even if manual)
- [ ] Rollout: `helm upgrade` → rolling update → zero dropped requests (verify with a `while curl` loop)

Next: `11-observability-metrics` — making the whole thing visible.
