# Tuning and Observability

> Worker counts, file-descriptor math, socket tuning, and the metrics that actually
> tell you what's happening at the edge. `docs/observability.md` §6 has a light
> version of the metrics list — this goes deeper on *what each metric means* and *what
what to do when it moves.*

---

## 1. Worker processes

```nginx
worker_processes auto;         # one per CPU core
worker_connections  1024;      # per worker
worker_rlimit_nofile 65535;    # per worker, must be ≥ worker_connections × 2

events {
    use epoll;                 # Linux; default on modern distros
    multi_accept on;
    worker_connections 1024;
    accept_mutex off;          # modern default; avoids global lock on accept
}
```

```
  ┌────────────────────────────────────────────────────────────────┐
  │  THE MATH:                                                      │
  │                                                                  │
  │  worker_rlimit_nofile = max FDs the worker can hold             │
  │     ≥ worker_connections   (each connection uses 2 FDs:         │
  │                             client side + upstream side)         │
  │                                                                  │
  │  So: worker_connections = 1024  →  worker_rlimit_nofile ≥ 2048  │
  │                                                                  │
  │  Max concurrent connections across the nginx instance:           │
  │     worker_processes × worker_connections                        │
  │     = 4 cores × 1024 = ~4,096 connections per worker set        │
  │                                                                  │
  │  The FD limit is per-PROCESS, not per-container. If your pod    │
  │  has a container-level FD cap (e.g. 1024), nginx can't exceed   │
  │  it regardless of config. Check with `cat /proc/self/limits`.   │
  └────────────────────────────────────────────────────────────────┘
```

**Common failure:** `worker_rlimit_nofile` exceeds the container's FD limit → nginx
fails to bind with an opaque "too many open files" or a worker crashes on load.

---

## 2. Socket tuning

```nginx
tcp_nopush          on;       # send complete responses in one packet
tcp_nodelay         on;       # disable Nagle's algorithm for interactive traffic
tcp_send_timeout    60s;
sendfile            on;       # use sendfile() for static files
sendfile_max_chunk  256k;     # limits how much one sendfile call can do
open_file_cache     max=1000 inactive=60s;   # cache file descriptors + metadata
open_file_cache_valid 30s;
keepalive_timeout   65s;      # idle client connection lifetime
keepalive_requests  1000;     # max requests per keepalive connection
```

**What each one actually changes:**

| Setting | Effect |
|---------|--------|
| `tcp_nopush` | For large responses, batches data so the kernel sends whole segments in one packet. Marginal for small JSON. |
| `tcp_nodelay` | Sends small acks/writes immediately. Disable Nagle for low-latency interactive (WebSockets, SSE, JSON APIs). |
| `sendfile` | Kernel-side file→socket copy for static files; bypasses userspace. Huge for UI asset serving. |
| `open_file_cache` | Keeps FDs + file metadata cached, avoiding repeated `open()` syscalls. |
| `keepalive_*` | Client-side keepalive. Too short → many handshakes; too long → wasted resources on idle conns. |

**The Nagle / TCP_NODELAY interaction:** `tcp_nodelay off` combined with delayed ACKs
from the peer can cause ~40ms stalls per request — the classic "why is my API slower
than it should be." For JSON APIs, keep `tcp_nodelay on`.

---

## 3. Metrics — the ones that matter

### The essential set

| Metric | What it means | Alert when |
|--------|---------------|-----------|
| **Request rate** (rps) | Traffic volume | sustained anomaly vs baseline |
| **5xx rate** | nginx is failing upstream | > 1% for 5 min |
| **4xx rate by code** | Client errors; a spike in 401/403 = auth problem, 429 = rate-limiting firing | > 5% of traffic or a sudden change |
| **P95/P99 request_time** | Client-perceived latency at the edge | regression vs baseline |
| **P95/P99 upstream_response_time** | App latency (before nginx overhead) | regression vs baseline |
| **Active connections** (`stub_status`) | Concurrent in-flight | > N× typical |
| **Rate-limit rejections** (`limit_req_status`) | The limiter is firing | sustained > 0 |
| **Cache hit ratio** | `hit / (hit + miss)` for `proxy_cache` | drop below 0.9 for static assets |
| **FD usage** (`open files` metric) | Proximity to `worker_rlimit_nofile` | > 80% |

### `stub_status` — the built-in metrics endpoint

```nginx
http {
    server {
        listen 127.0.0.1:8090;   # bound to loopback — never expose
        allow 127.0.0.1;
        deny  all;
        location /stub_status {
            stub_status;
        }
    }
}
```

```
Active connections: 42               ← currently in-flight
server accepts handled requests
 38291  38291  76582;                ← accepts / handled / total requests
Reading:   3 Writing: 11 Waiting: 28 ← state breakdown
```

In production you almost always use the **NGINX Prometheus exporter** (a Go sidecar
running nginx as a library) instead of `stub_status`. It exposes everything below as
proper Prometheus metrics with labels.

### What each exporter metric actually tells you

```
  ┌──────────────────────────────────────────────────────────────────┐
  │  nginx_http_requests_total{handler,code,status}                  │
  │    • code + status together: a 4xx means CLIENT problem,         │
  │      5xx means SERVER/upstream problem.                          │
  │    • group by handler to find the noisy endpoint.                │
  ├──────────────────────────────────────────────────────────────────┤
  │  nginx_http_request_duration_seconds                              │
  │    • client-perceived latency at the edge                        │
  │    • compare to nginx_http_upstream_response_time_seconds —      │
  │      the delta is nginx overhead (usually tiny)                  │
  ├──────────────────────────────────────────────────────────────────┤
  │  nginx_http_requests_per_second                                 │
  │    • traffic shaping; alert on sustained > your capacity         │
  ├──────────────────────────────────────────────────────────────────┤
  │  nginx_connections_active                                       │
  │    • current concurrency. Combined with request rate, tells you  │
  │      whether you're bound on throughput or latency.              │
  ├──────────────────────────────────────────────────────────────────┤
  │  nginx_limit_req_status                                         │
  │    • the rate-limiter is firing. Non-zero sustained = a caller   │
  │      is being throttled. Alert.                                  │
  └──────────────────────────────────────────────────────────────────┘
```

---

## 4. The pipeline to Grafana/Datadog

```
  ┌────────────┐    ┌────────────────────┐    ┌─────────────┐    ┌────────────┐
  │  nginx     │──► │ Prometheus exporter│──► │ Prometheus  │──► │  Grafana   │
  │  metrics   │    │ (sidecar, nginx lib)│    │ (scrape)    │    │  (panels) │
  └────────────┘    └────────────────────┘    └─────────────┘    └────────────┘
                                                              └───► Datadog API
                                                                   (remote write)
```

**For this project:** Datadog's agent can either scrape Prometheus endpoints or you
can remote-write. The important thing is the labels — keep a low-cardinality label set
(host, path-prefix, status class) and reserve high-cardinality fields (user ID, exact
URL) for logs, not metrics.

---

## 5. Log-driven observability

The access log is not just for forensics — it's a first-class observability source.
Structured JSON logs feed Datadog Logs directly.

```
  ┌───────────────────────────────────────────────────────────────┐
  │  Metric (aggregated)  │  Log (individual events)               │
  │                        │                                        │
  │  "avg latency 200ms"  │  "request 4211 took 3.2s and hit      │
  │  "1% 5xx rate"        │   upstream timeout on /api/expenses   │
  │                        │   for user X"                          │
  │                        │                                        │
  │  Metrics tell you WHAT │  Logs tell you WHICH request and WHY  │
  └───────────────────────────────────────────────────────────────┘
```

Both are needed. Metrics alone can't answer "which specific slow query hit this"; logs
alone can't answer "has our P99 been creeping up this week."

---

## 6. Config-debugging workflow

```
  1. EDIT nginx.conf or annotation
  │
  2. VALIDATE without reloading:
  │      nginx -t
  │    "syntax is ok / test is successful"  → safe to reload
  │    "emerg: ..."                         → DO NOT reload, fix it
  │
  3. RELOAD (graceful):
  │      nginx -s reload     (or SIGHUP, or kubectl rollout restart)
  │    → old workers drain existing connections; new workers start
  │    → zero dropped connections
  │
  4. VERIFY:
  │      nginx -T 2>/dev/null | grep <your_setting>
  │      tail -f /var/log/nginx/error.log
  │
  5. WATCH:
         metrics — request rate, 5xx, latency
```

**Why reload is safe:** nginx reloads by starting new workers that read the new config,
and telling old workers to stop accepting but finish current requests. See
[`architecture.md`](architecture.md) for the process model.

---

## 7. Interview angle

- **"How many connections can nginx handle?"** — `worker_processes × worker_connections`
  per worker set, capped by the per-process FD limit. Show the math.
- **"What's the difference between active connections and request rate?"** — concurrency
  vs throughput; different failure modes (bound on FD vs bound on CPU).
- **"How do you know nginx is having problems vs the upstream?"** — compare nginx's
  request latency to `upstream_response_time_seconds`. Delta is nginx; upstream time is
  the app.
- **"How do you safely change nginx config?"** — `nginx -t` first, then reload; reload
  is graceful because old workers drain.

---

## 8. How this shows up here

- With a small single-node cluster you'll start with `worker_processes auto` and
  `worker_connections 1024`, then tune upward only if you see FD pressure.
- Metrics go to Datadog via the Datadog agent's Prometheus check (or the built-in
  nginx integration).
- Alert thresholds (record in `design.md`):
  - 5xx rate > 1% for 5 min
  - P95 latency > 2s for 5 min
  - `limit_req_status` non-zero for > 1 min
  - FD usage > 80% of limit
- The correlation ID flow documented in [`security-and-headers.md`](security-and-headers.md)
  is what makes "which request was slow" answerable.
