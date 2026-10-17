# Rate Limiting in NGINX

> NGINX's *implementation* of rate limiting. The algorithms themselves (fixed window,
> token bucket, leaky bucket, GCRA, distributed limiters) are in
> [`../rate-limiting.md`](../rate-limiting.md) — read that first if you haven't. This
> doc is what you actually configure.

---

## 1. The two modules

```
  limit_req      →  REQUEST RATE   ("N requests per second")
  limit_conn     →  CONNECTIONS    ("M concurrent connections")

  Both use a shared-memory ZONE defined in http{} and referenced in server/location{}.
```

---

## 2. `limit_req` — request rate (a leaky bucket)

### The zone

```nginx
http {
    #  shared zone: key = client IP, state = tokens, 10 MB holds ~160k keys
    limit_req_zone  $binary_remote_addr  zone=api_perip:10m  rate=20r/s;

    server { ... }
}
```

| Parameter | Meaning |
|-----------|---------|
| `$binary_remote_addr` | the key. Binary form — no wasted bytes on `127.0.0.1` vs `::ffff:127.0.0.1`. |
| `zone=NAME:SIZE` | shared memory. **160K keys per MB.** Size it to expected key count. |
| `rate=20r/s` | the sustained rate. Also `1r/m`, `1r/d`, `100r/h`. |

### The directive

```nginx
location /api/ {
    limit_req zone=api_perip burst=40 nodelay;
}
```

### `burst` and `nodelay` — the part everyone gets wrong

```
  burst=N means "hold N extra requests in a queue"

  ┌─────────────────────────────────────────────────────────────┐
  │                                                             │
  │  WITHOUT nodelay  (classic leaky bucket)                    │
  │    requests beyond rate are QUEUED, then DRAINED at `rate`   │
  │    → a burst of 40 all succeeds, but they're spaced out     │
  │                                                             │
  │  WITH nodelay                                             │
  │    requests beyond rate are accepted IMMEDIATELY (no wait)  │
  │    → a burst of 40 all succeed AT ONCE                     │
  └─────────────────────────────────────────────────────────────┘

  burst = 0 (default)  →  NOTHING extra allowed. Strict rate.
  burst = 40           →  40 above `rate` accepted in a burst
  nodelay              →  the burst is served instantly, not drained
```

**Worked example — 5 requests/second, burst=4, nodelay, at t=0 a client sends 6 in 1ms:**

```
  rate = 5/s, burst = 4, nodelay

  t=0.000s   req 1  → allowed   (bucket had 5 tokens from prior refills)
  t=0.000s   req 2  → allowed   (bucket 4)
  t=0.000s   req 3  → allowed   (bucket 3)
  t=0.001s   req 4  → allowed   (bucket 2)
  t=0.001s   req 5  → allowed   (bucket 1)
  t=0.001s   req 6  → allowed   (bucket 0, burst=4 lets it through with nodelay)

  t=0.500s   req 7  → REJECTED (bucket has refilled ~2.5; but the burst pool is
                                     exhausted AND we're at rate now)

  Without nodelay, reqs 3-6 would have been QUEUED and sent at ~200ms intervals,
  arriving to the client at t=0, t=200, t=400, t=600 — same count, smoother arrival.
```

**When to use which:**

| Mode | Behavior | Use for |
|------|----------|---------|
| `burst=0` | strict, every extra rejected | hard limits, per-login throttles |
| `burst=N` (no nodelay) | extra **queued**, drained slowly | shaping traffic, absorbing micro-bursts smoothly |
| `burst=N nodelay` | extra **immediately accepted** | user-friendly: tolerate a UI that fires N parallel requests |

**This project:** the SPA fires ~5 parallel requests on page load. `burst=40 nodelay`
is the sane choice — the burst goes through instantly and the user sees nothing wrong.
`burst=0` would 429 their own UI.

### The zone key problem

```
  ┌──────────────────────────────────────────────────────────────┐
  │  $binary_remote_addr = the immediate TCP peer                │
  │                                                               │
  │  Behind ANOTHER proxy (like Tailscale → LB → nginx):         │
  │    $remote_addr = the LB's IP, not the real client!           │
  │    → EVERYONE is rate-limited as ONE client                   │
  │                                                               │
  │  FIX: trust the right X-Forwarded-For hop                     │
  │                                                               │
  │    set_real_ip_from  10.42.0.0/16;        # trusted proxy CIDR│
  │    real_ip_header    X-Forwarded-For;     # read from header   │
  │    real_ip_recursive on;                  # walk back          │
  │                                                               │
  │  Only then does $binary_remote_addr reflect the real client. │
  │  (See the trust-boundary discussion in reverse-proxy.md §7.) │
  └──────────────────────────────────────────────────────────────┘
```

### Response on rejection

```nginx
limit_req_status  429;      # default is 503 — pick 429 for rate limiting
proxy_hide_header X-RateLimit-Limit;
add_header  X-RateLimit-Limit       600 always;
add_header  X-RateLimit-Remaining   $limit_req_status always;
add_header  Retry-After             1 always;
```

Use **429** for "you're sending too much" (client should back off) and **503** for "I'm
overloaded" (server problem) — see [`../rate-limiting.md`](../rate-limiting.md) §4 for
why mixing them up makes retry logic misbehave.

---

## 3. `limit_conn` — concurrent connections

```nginx
http {
    limit_conn_zone $binary_remote_addr zone=conn_perip:10m;
}

server {
    limit_conn conn_perip 10;    # at most 10 concurrent connections per key
    limit_conn_status 503;
}
```

**Different job:** limits *concurrency* (how many things in flight at once), not *rate*.
A slow client making one request every 30s never trips `limit_req` but *does* trip
`limit_conn` if they keep 20 connections open. Use both: rate limits prevent abuse
bursts, connection limits prevent slow-client exhaustion.

---

## 4. Ingress-nginx annotations

In k3s you don't write `http{}` — you annotate Ingress resources. The controller
renders the equivalent config.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api
  annotations:
    # request rate: 20 r/s, burst 40
    nginx.ingress.kubernetes.io/limit-rps:              "20"
    nginx.ingress.kubernetes.io/limit-rpm:              "1200"
    nginx.ingress.kubernetes.io/limit-connections:      "10"
    # the per-path key (default: remote_addr; here: user from a header if you like)
    nginx.ingress.kubernetes.io/limit-key:              "$remote_addr"
    # status code + response headers on limit
    nginx.ingress.kubernetes.io/limit-req-status:       "429"
    nginx.ingress.kubernetes.io/limit-req-header-fields: "X-RateLimit-Remaining, Retry-After"
spec:
  ingressClassName: nginx
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: expense-api
                port:
                  number: 8000
```

**Note the annotation names:** they are `limit-rps`, `limit-connections`, etc. — not
nginx directives. The controller does the mapping.

---

## 5. Where this lives in the stack

```
  ┌────────────────────────────────────────────────────────────────┐
  │                                                                │
  │   LAYER 1: NGINX  (per-IP, coarse, survives anything upstream) │
  │          • can't know WHO the user is (no auth yet)            │
  │          • job: shed unauthenticated floods before they cost   │
  │            Python anything                                       │
  │                                                                │
  │   LAYER 2: DRF    (per-USER, semantic)                          │
  │          • knows WHO (JWT validated)                            │
  │          • job: per-user semantic throttles — login stricter   │
  │            than reads, per-user-not-IP                          │
  │                                                                │
  └────────────────────────────────────────────────────────────────┘

  Neither replaces the other:
    • per-IP can't express "strict for logins, generous for reads"
    • per-user can't stop unauthenticated floods
```

This is the recurring checkpoint question — see
[`../checkpoints.md`](../checkpoints.md) and
[`../drf-jwt-guide.md`](../drf-jwt-guide.md) §6.

---

## 6. Interview angle

- **"How do you rate-limit in nginx?"** — `limit_req_zone` in `http{}` defining a
  shared-memory zone keyed by IP; `limit_req` in a location references it, with
  `burst` and `nodelay` tuning.
- **"What's the difference between burst and nodelay?"** — burst sets the queue size;
  nodelay decides whether the queue is served instantly or drained slowly.
- **"Client gets 429 — why?"** — the key's bucket is empty and the burst is exhausted.
- **"How do you key by user, not IP, behind a proxy?"** — `set_real_ip_from` +
  `real_ip_header` so `$binary_remote_addr` reflects the real client; or
  ingress annotation `limit-key`.
- **"429 or 503?"** — 429 for rate limit (client's fault), 503 for overload (server's
  fault).

---

## 7. How this shows up here

- Phase 11 configures an ingress-nginx annotation like §4 for `/api`.
- The `burst` value must accommodate the UI's parallel request burst — a burst too
  small 429s your own frontend.
- The value to record in `design.md`: rate, burst, and per-endpoint overrides (if any).
- Layered with DRF per-user throttling — see the two-layer diagram above.
