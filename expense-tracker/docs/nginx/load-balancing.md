# Load Balancing

> How NGINX picks which upstream gets each request, when each algorithm is right, why
> sticky sessions are usually wrong for stateless APIs, and how a rollout stays
> zero-downtime.

---

## 1. The upstream block

```nginx
upstream expense_api {
    #   server ADDRESS            [WEIGHT] [PARAMS];
    server 10.42.1.5:8000;
    server 10.42.1.6:8000;
    server 10.42.1.7:8000;
}
```

In Kubernetes you don't hardcode pod IPs — the **Service** DNS name resolves to the
current set of endpoints, and the ingress controller watches **EndpointSlices** to keep
this list fresh (see [`ingress-in-k3s.md`](ingress-in-k3s.md)).

---

## 2. The algorithms

### 2.1 Round-robin (default)

Requests go to each server in turn.

```
  req#:  1   2   3   4   5   6   7   8   9
  pod:   A   B   C   A   B   C   A   B   C      (equal weight)

  Weighted:  server A weight=2;  server B weight=1
  req#:  1   2   3   4   5   6   7   8   9
  pod:   A   A   B   A   A   B   A   A   B
```

- **Use:** homogeneous backends, similar request cost.
- **Weakness:** if requests have wildly different costs, round-robin distributes
  *requests*, not *load* — a slow endpoint on one pod still gets its turn.

### 2.2 `least_conn`

Send to the upstream with the **fewest active connections**.

```
  Active conns:   A=5   B=1   C=8
  next request ──► B       (fewest active)

  Active conns:   A=5   B=1   C=8   (B just took one)
  next request ──► B  (now 2) or A?  → whichever is lower
```

- **Use:** **request cost varies a lot** (some requests are slow reports, some are fast
  reads). This is usually the right default for an API where a few endpoints are heavy.
- **Why it often beats round-robin:** a pod stuck on a slow query naturally receives
  fewer new requests, so it self-balances.

### 2.3 `ip_hash`

Hash the client IP → same client always hits the same backend.

```
  client_ip ──► hash() ──► pod index
   10.0.0.5  ──► 0x82.. ──► A       every request from 10.0.0.5 → A
   10.0.0.9  ──► 0x1a.. ──► B       every request from 10.0.0.9 → B
```

- **Use:** legacy **stateful** backends that keep session state in-process (a servlet
  with an HTTP session). 
- **Problem:** if pod A dies, **every 10.0.0.5 user loses their session** until A
  returns. And NAT'd clients (a whole office behind one IP) all pile onto one pod.
- **This project:** ✗ **not needed** — auth is **JWT**, which is stateless, so any pod
  can serve any request. Sticky sessions would be pure downside.

### 2.4 `hash` (custom key)

```nginx
upstream expense_api {
    hash $http_authorization consistent;   # or $cookie_session, $arg_user_id, etc.
    server 10.42.1.5:8000;
    server 10.42.1.6:8000;
}
```

- **Use:** you need affinity by something other than IP (user id, API key) for cache
  locality or sharded state.
- **Consistent hash** (`consistent` keyword): only ~1/N of keys remap when a server
  joins/leaves, vs a naive hash which remaps almost everything.
- **Downsides:** **hot partitions** (one very active user dominates one pod — see the
  Kafka partition-key discussion in [`../kafka-guide.md`](../kafka-guide.md)); and if
  the system is actually stateless, you've added a failure mode for nothing.

### 2.5 The comparison

| Algorithm | Distributes by | Best when | Failure behavior |
|-----------|----------------|-----------|------------------|
| round-robin | request count | uniform cost | fine (just re-deal) |
| least_conn | active connections | **variable cost** | self-balancing |
| ip_hash | client IP | stateful sessions | clients lose session on pod death |
| hash (consistent) | custom key | cache/shard affinity | ~1/N keys remap |
| least_time | fastest response | latency-sensitive | picks the responsive pod |

**For this project:** `least_conn` (or round-robin if all endpoints are cheap). Never
`ip_hash` — the API is stateless.

---

## 3. Health checks

### Passive (default) — free, reactive

```nginx
upstream expense_api {
    server 10.42.1.5:8000 max_fails=3 fail_timeout=10s;
    #                     └─────────┘ └────────────┘
    #   after 3 failures within 10s, mark unhealthy for 10s
    server 10.42.1.6:8000;
}
```

```
  ┌──────────────────────────────────────────────────────────────┐
  │  PASSIVE HEALTH-CHECK STATE MACHINE                           │
  │                                                               │
  │        ┌──────────┐   fail_count ≥ max_fails                 │
  │        │ HEALTHY  │ ──────────────────────► ┌────────────┐   │
  │        │ (in LB)  │                          │ UNHEALTHY  │  │
  │        └────▲─────┘                          │ (skipped)  │  │
  │             │                                 └─────┬──────┘ │
  │             │     fail_timeout elapses,              │        │
  │             └──── next request probes it ────────────┘        │
  │                   (success → HEALTHY, fail → back to UNHEALTHY)│
  └──────────────────────────────────────────────────────────────┘

  Note: "UNHEALTHY" ≠ removed. nginx still lets ONE request through
  per fail_timeout to test if the server recovered (probing).
```

- **Cost:** zero — nginx just watches real responses.
- **Weakness:** a dead server is discovered only when a real client request fails
  (`max_fails` times).

### Active (NGINX Plus only, or ingress-nginx annotation restarts)

NGINX Plus and some ingress setups do **out-of-band health probes** (a `/healthz`
request every N seconds) so a dead pod is removed *before* a client hits it. OSS nginx
relies on passive checks; the ingress controller compensates by watching the
**EndpointSlice** — when k8s removes a pod from the Service, the controller regenerates
the upstream and drops it (see [`ingress-in-k3s.md`](ingress-in-k3s.md)).

**This project's API should expose `/healthz`** (liveness) and `/readyz` (readiness).
Kubernetes uses them to manage endpoints; the readiness gate is what keeps nginx from
routing to a pod that isn't ready yet.

---

## 4. Zero-downtime rollout — the sequence

The subtlety: **k8s removing a pod from endpoints and nginx removing it from its
upstream are not the same instant.** There's a window where nginx still lists a pod
that k8s has already drained.

```
  t0  Rolling update starts. New pod N+1 created.
  │
  t1  N+1 passes readiness. Added to EndpointSlice.
  │
  t2  Controller regenerates upstream → nginx starts sending to N+1.
  │
  t3  Old pod N marked for termination. Removed from EndpointSlice.
  │
  t4  Controller reloads nginx → N removed from upstream.
  │        ┌─────────────────────────────────────────────────┐
  │        │  DANGER WINDOW (t3 → t4):                        │
  │        │  nginx still lists N, but N is shutting down.    │
  │        │  If nginx sends a request to N now → 502.        │
  │        └─────────────────────────────────────────────────┘
  │
  t5  N's `preStop` hook + `terminationGracePeriodSeconds` let it
      finish in-flight requests. This is the pod's job to get right.
  │
  t6  N gone. Rollout complete. Zero client-visible errors.
```

**Requirements for the clean version:**

1. **Readiness probe** so N+1 joins only when actually ready.
2. **`preStop` hook + graceful shutdown** in the app: stop accepting, finish in-flight,
   exit after `terminationGracePeriodSeconds`. (Gunicorn needs a graceful timeout that
   matches — a mismatch here is a common dropped-request source.)
3. **A small `sleep` in `preStop`** so the EndpointSlice update propagates to nginx
   *before* the app stops accepting.
4. **`proxy_next_upstream error timeout`** as a backstop — if a request *does* hit a
   draining pod, nginx retries the next one (only for idempotent requests).

**One replica:** there is no "rolling" — the single pod goes down and back up, and
requests during the gap fail. This is the honest cost of the single-node setup; a
second replica is what buys real zero-downtime (and is worth it before you call the
system "production-shaped").

---

## 5. Interview angle

- **"round-robin vs least_conn?"** — request count vs active connections. least_conn
  self-balances when request costs vary.
- **"Why not sticky sessions?"** — they're a workaround for stateful backends; a
  stateless API (JWT) needs no affinity, and stickiness adds a "clients drop on pod
  death" failure mode for nothing.
- **"How do you deploy with zero downtime?"** — readiness gate + graceful shutdown +
  EndpointSlice propagation + `preStop` delay; name the danger window between endpoint
  removal and nginx reload.
- **"What happens to in-flight requests when a pod is removed?"** — the pod's
  `preStop`/grace period finishes them; nginx may retry idempotent ones.

---

## 6. How this shows up here

- Algorithm choice (`least_conn`) goes in `design.md`; it matters once there's more
  than one API replica.
- The API must expose `/healthz` and `/readyz` — the readiness gate is what makes
  rollouts safe.
- Gunicorn's graceful timeout must match the pod's `terminationGracePeriodSeconds`; a
  mismatch is a real dropped-request bug.
- Sticky sessions: explicitly rejected, because JWT is stateless —
  [`../drf-jwt-guide.md`](../drf-jwt-guide.md) §4.
