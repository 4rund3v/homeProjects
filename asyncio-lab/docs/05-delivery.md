# 05 — Delivery: `uv`, Docker, and a k8s Service

The *tool* is the point. This doc is the *delivery layer* you asked for: `uv` for the environment, a *container* for portability, and a *k8s Service* so the tool is *reachable* and *probeable* like a *real* *service*. Read it last; it is *delivery*, not *concurrency understanding*.

## `uv` — the env, not the code

*The* *workspace root* *has* *`uv-setup.md`*. *This* *project* *is* *`uv`-managed: `uv lock`, `uv sync`, and* **`uv run`** *for every execution* (never* *bare* *`python`, so the* *venv* *and* *the* *lock* *are honored).*

*The* *`pyproject.toml`:*

```toml
[project]
name = "asyncio-lab"
version = "0.1.0"
requires-python = ">=3.11"          # TaskGroup + to_thread ergonomics
dependencies = []                    # the dup tool is stdlib-only on purpose

[project.scripts]
dupfind = "cmd.dupfind.main:cli"
```

*Stdlib-only* *is* *a* *feature* *for* *this* *learning* *tool:* *no* *dependency* *means* *the* *concurrency* *you* *measure* *is* *purely* *asyncio +* *the* *process pool*, *not a* *library* *hiding the* *work*. *The* *only* *third-party* *thing you* *would* *add* *is* *a* *faster* *I/O* *backend (`uvloop`/aiofiles), and even that is optional.*

## Docker — the *container* is a *probe*, not a *dependency*

*The point of* *containerizing* *a CLI* *tool is to* *prove* *it is* *self-contained* (no host *python* *needed) and* *to* *expose it as a service* *with a live probe.* *The* *Dockerfile:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
# uv is available in the build via a one-shot install:
RUN pip install uv && uv sync --frozen
COPY cmd/ cmd/
COPY internal/ internal/
# entrypoint: run the CLI
ENTRYPOINT ["uv","run","dupfind"]
```

*The* *container* *holds the* *tool; it* *does not* *hardcode* *a* *directory* *to scan.* *The* *target directory* *comes* *in* *as* *an argument* (a mounted volume or a *remote* *source*).

## k8s — the *Service* is for *reachability + a probe*, not *because we need k8s*

*The* *anti-pattern* *is "wrap a CLI in k8s."* *The* *right* *reason* *here: expose* *a thin HTTP surface that runs a scan on demand and reports*, so *a dashboard* or *a cron* *can* *trigger it* *and* *the* *Service + readiness probe* *make it a* *first-class service* *in the cluster.*

*The shape:*

```
Deployment (dupfind app)
   │  1 replica (the pool is in-process; scale = workers, not pods)
   │
   ├─ container: runs `uv run dupfind --serve`  (a tiny http server)
   │
   Service (dupfind)
      ├─ selector: app=dupfind
      ├─ port 8080 → container 8080
      │
      └─ readinessProbe:  GET /healthz  (returns 200 when the pool is up)
```

*The* *`--serve`* *mode* *is the* *one* *addition to* *the* *tool:* *an `aiohttp` (or stdlib `http.server`)* *endpoint:*

- *`GET /healthz`* → `200` *when* *the* *process pool is* *initialized.*
- *`POST /scan`* → *body = target dir (or a mount ref),* *returns* *the duplicate* *groups as* *JSON.*

*The* *readiness* *probe* *on* *`/healthz`* *is* *the* *k8s* *concept* *you* *are* *really* *learning: "is this pod ready to take traffic?"* — *the exact same* *question* *`traffic-analysis/load-balancing/03`* *asks of* *NGINX*, *one* *layer* *up.*

*The* *`k8s.yaml`* (kept minimal, for learning):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: dupfind }
spec:
  replicas: 1
  selector: { matchLabels: { app: dupfind } }
  template:
    metadata: { labels: { app: dupfind } }
    spec:
      containers:
      - name: dupfind
        image: dupfind:0.1.0
        ports: [{ containerPort: 8080 }]
        readinessProbe:
          httpGet: { path: /healthz, port: 8080 }
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata: { name: dupfind }
spec:
  selector: { app: dupfind }
  ports: [{ port: 8080, targetPort: 8080 }]
```

*The* *single* *replica* *is* *deliberate:* *the* *process* *pool* *is* *in-process.* *Scaling* *out to* *N* *pods* *would* *give* *N* *independent* *pools* — *for* *a* *learning* *tool*, *that is* *more* *surface* *than* *you need. If* *you do* *scale* *out, the* *correct* *move is a* *central coordinator that* *fans out* *the work across* *the pods* (a* *`02`* *worker-pool* *across* *the network), and the* *duplicate grouping* *must* *merge* *across pods* — *the same* *`04`* *invariant*, *one* *layer* *up.*

## What the *k8s* *addition* *teaches* that the *CLI* *does not*

1. **A probe is a *senior* health check.** The `readinessProbe` is *literally* the L7 health check from `traffic-analysis/load-balancing/02`, *at* *the* *container level*. The *concepts* *link across* *the two* *repos*: *a* *service* *that is "up" (pod running) but not "ready" (pool not initialized) is* *the same* *L4-up/L7-down* *state* *`load-balancing/03`* *describes.*
2. **A container is a *capability boundary*.** The *dup* *tool runs with* *a mounted volume* + *a* *CPU limit.* The *process pool's `max_workers`* *must* *respect* *the pod's* *`limits.cpu`* — *8* *workers on a* *2-core pod is* *oversubscription*, *the exact* *CPU-saturation* *from* *`traffic-analysis/capacity/01`.*
3. **`uv` + a *lock* = reproducible delivery.** The *`uv sync --frozen`* *in the Dockerfile* *is the same idea as a pinned image tag in `traffic-analysis/project/labs/registry.md` — no *float, no surprise.*

## The *end-to-end* run

```
uv run dupfind /data          # the CLI (local)
uv run dupfind --serve        # the service (the container entrypoint)
kubectl get svc dupfind       # the Service
curl localhost:8080/healthz   # the probe
curl -XPOST localhost:8080/scan -d '{"dirs":["/data"]}'   # the scan (note: "dirs", a list)
```

*The last line is the whole point: the same concurrency work (stages 1-4) is now triggered over HTTP, behind a probe, in a container, in a cluster.* *Nothing about the async code changed — only the delivery surface did.* *That separation ("concurrency logic" vs "delivery") is the senior read this folder ends on.*

## What is actually verified, on a box with no docker/kubectl

So the reader knows which layer of the delivery path is *proven* vs *written-but-untested*:

| Layer | Verified? | How |
|---|---|---|
| `uv lock` → `uv sync` → `uv run dupfind` | **yes** | ran it; the installed entrypoint finds the dup group |
| `--serve` + `GET /healthz` + `POST /scan` | **yes** | ran it locally; clean JSON on both endpoints, 400 on bad input |
| the concurrency invariant (output independent of worker count) | **yes** | `tests/test_invariant.py` passes at cap=1 and cap=8 |
| `Dockerfile` build | **no** | no docker here. Written to `python:3.11-slim` + `uv sync --frozen`; *build it where docker exists* |
| `k8s.yaml` deploy | **no** | no kubectl/k3s here. The *manifest* is conventional; *the readiness probe* is the thing to check first on a real cluster |

*The honest line:* **the async code and the HTTP surface are proven; the container and the cluster are *designed*, not *verified*.** That split is itself the lesson — the concurrency logic is *portable* and *testable* without a cluster, and the *delivery* is a *separate* concern you attach at the edge.
