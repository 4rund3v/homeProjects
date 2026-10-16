# NGINX as a Reverse Proxy

> How a client request becomes an upstream request and back — with the config traps
> that cause most production bugs. The proxy is where the edge's *policy* (TLS, limits,
> headers) meets the *routing* (which backend gets this).

---

## 1. Reverse proxy vs forward proxy

```
  FORWARD PROXY (client-side)                 REVERSE PROXY (server-side)
  ────────────────────────────                ─────────────────────────────
  clients ──► proxy ──► the internet          the internet ──► proxy ──► servers

  ┌──────┐   ┌───────┐   ┌──────────┐         ┌──────┐   ┌───────┐   ┌─────────┐
  │client│──►│forward│──►│  origin  │         │client│──►│reverse│──►│ backend │
  │      │   │ proxy │   │  server  │         │      │   │ proxy │   │  pool   │
  └──────┘   └───────┘   └──────────┘         └──────┘   └───────┘   └─────────┘
  • represents the CLIENT                     • represents the SERVERS
  • hides the client from servers             • hides the servers from clients
  • egress filtering, anonymity               • ingress, LB, TLS, caching, WAF
  • corporate egress proxy, VPN               • nginx / ingress  ← THIS project
```

Both are "a proxy." The word that matters is *which side it speaks for*.

---

## 2. The request flow

```
   ┌────────┐        ┌─────────────────────────┐        ┌──────────────┐
   │ client │        │        NGINX            │        │   upstream   │
   │        │        │  (ingress pod, k3s)     │        │  (DRF API)   │
   └───┬────┘        └────────────┬────────────┘        └──────┬───────┘
       │                          │                            │
       │ 1. TCP + TLS handshake   │                            │
       │─────────────────────────►│                            │
       │                          │                            │
       │ 2. HTTP request          │                            │
       │─────────────────────────►│                            │
       │                          │ 3. apply edge policy:      │
       │                          │    • rate limit (limit_req)│
       │                          │    • rewrite headers       │
       │                          │    • choose upstream (LB)  │
       │                          │                            │
       │                          │ 4. open/reuse upstream conn│
       │                          │───────────────────────────►│
       │                          │    (plain HTTP inside)     │
       │                          │                            │
       │                          │ 5. upstream response       │
       │                          │◄───────────────────────────│
       │                          │                            │
       │ 6. response (TLS)        │  • add security headers    │
       │◄─────────────────────────│  • maybe transform/gzip    │
       │                          │                            │
```

**Key fact:** after TLS termination (§1 of `../tls/`), everything from nginx to the
upstream is **plain HTTP inside the pod network**. The encryption boundary is between
client and *nginx*, not client and app.

---

## 3. The core directive: `proxy_pass`

```nginx
location /api/ {
    proxy_pass http://api-svc.default.svc.cluster.local:8000/;
    #                                                       ^ trailing slash!
}
```

### The URI-substitution trap (memorize this)

Whether `proxy_pass` has a **trailing slash** decides whether nginx **replaces** the
matched location prefix or **passes it through**:

```
  location /api/  {  proxy_pass http://backend:8000;   }   ← NO trailing slash
  location /api/  {  proxy_pass http://backend:8000/;  }   ← trailing slash

  Request:  GET /api/v1/expenses

  NO slash  → /api/v1/expenses        (prefix PRESERVED; backend sees /api/v1/expenses)
              because the URI is appended as-is

  SLASH     → /v1/expenses            (prefix REPLACED by "/")
              because /api/ is replaced with /, the rest appended
```

**The rule:** the part of the request URI matching the `location` is replaced by the
URI in `proxy_pass`. No URI in `proxy_pass` → the full path is passed. This single
distinction causes a huge share of "404 from the backend" bugs.

```
  CHEAT SHEET
  ───────────
  proxy_pass http://upstream;          → pass the full original path
  proxy_pass http://upstream/;         → strip the location prefix, replace with /
  proxy_pass http://upstream/api/;     → strip the prefix, replace with /api/
  proxy_pass http://upstream$request_uri;  → explicit, pass everything
```

**Rule of thumb for this project:** if DRF serves `/api/v1/...` and your Ingress path
is `/api`, use a `rewrite-target` annotation (see [`ingress-in-k3s.md`](ingress-in-k3s.md))
rather than fighting the trailing-slash rule — the controller generates cleaner config.

---

## 4. The three timeouts (and why each is different)

```nginx
proxy_connect_timeout 5s;   # time to establish the TCP connection to the upstream
proxy_send_timeout    60s;  # time between successive WRITES to the upstream
proxy_read_timeout    60s;  # time between successive READS from the upstream
```

```
  ┌──────────────────────────────────────────────────────────────────┐
  │  connect_timeout                                                  │
  │    client → nginx → [SYN] → upstream ... waiting for [SYN-ACK]    │
  │    "is the backend even reachable / accepting connections?"       │
  │    Short (2-5s). A backend that can't accept fast is unhealthy.   │
  ├──────────────────────────────────────────────────────────────────┤
  │  send_timeout  (between writes, not total)                        │
  │    nginx ──write── waiting ──write── waiting ──write             │
  │    "is the backend draining what I'm sending?"                    │
  ├──────────────────────────────────────────────────────────────────┤
  │  read_timeout  (between reads, not total)                         │
  │    upstream ──chunk── waiting ──chunk── waiting ──chunk          │
  │    "is the backend still producing my response?"                  │
  │    ★ This is the one you usually tune. Slow reports need more.    │
  └──────────────────────────────────────────────────────────────────┘
```

**Critical nuance:** `send`/`read` timeouts are **inactivity** timeouts — the timer
resets on every byte. A report that streams for 5 minutes but sends a byte every 10s
never trips a 60s read timeout. A report that goes silent for 61s does.

**This project:** a "spending by category this year" report might legitimately take 10s.
Don't set `proxy_read_timeout` to 5s globally; either raise it for the report location
or make the report async. Raising it globally means a hung backend ties up a worker
connection for the whole timeout.

---

## 5. Buffering — when to turn it off

```
  BUFFERING ON (default)                 BUFFERING OFF (proxy_buffering off)
  ──────────────────────                 ────────────────────────────────────
  upstream ──► nginx buffer ──► client    upstream ──► nginx ──► client (stream)

  nginx reads the WHOLE response from     nginx relays bytes as they arrive.
  upstream as fast as it can, into        The client waits for upstream's slow
  memory/disk, then serves the client     first byte. No disk buffer.
  at the client's pace.

  ✓ frees the upstream connection fast     ✓ true streaming (SSE, long-poll)
  ✓ smooths slow clients                   ✓ lower latency to first byte
  ✗ buffers large responses to DISK        ✗ upstream connection held for the
    (proxy_temp_path)                        whole client transfer
  ✗ breaks streaming (buffers until full)  ✗ a slow client can tie up upstream
```

**Turn buffering OFF for:**

```nginx
location /api/events/ {          # Server-Sent Events / streaming
    proxy_buffering off;
    proxy_cache off;
    proxy_set_header Connection "";
    chunked_transfer_encoding on;
}
```

**Keep it ON for** normal JSON APIs — buffering lets nginx free the upstream sooner
and protects against slow clients.

**Large request bodies:** `proxy_request_buffering off;` streams the *request* body
straight to the upstream instead of buffering it first — needed for big uploads where
you don't want nginx to write the body to disk first. Not needed for this project's
small JSON payloads, but worth knowing.

---

## 6. Upstream keepalive (connection reuse)

By default, nginx opens a **new TCP connection** to the upstream for every request.
That's a full handshake (and, inside a cluster, extra latency + TIME_WAIT sockets).
Keepalive to upstreams reuses connections:

```nginx
upstream api_backend {
    server 10.42.1.5:8000;
    server 10.42.1.6:8000;
    keepalive 32;               # pool of 32 idle keepalive conns per worker
}

server {
    location /api/ {
        proxy_pass http://api_backend;

        # ★ the gotcha: you MUST set the Connection header, or keepalive is ignored
        proxy_http_version 1.1;              # keepalive needs HTTP/1.1
        proxy_set_header Connection "";      # clear "close" so upstream keeps it open
    }
}
```

```
  WITHOUT keepalive          WITH keepalive (16 conns)
  ─────────────────          ────────────────────────
  req1 ─► [conn, close]      req1 ─► [conn]────┐
  req2 ─► [conn, close]      req2 ─────────────┤ reuse
  req3 ─► [conn, close]      req3 ─────────────┘
  3 handshakes               1 handshake, 3 requests
```

**The two gotchas that silently disable keepalive:**

1. Forgetting `proxy_http_version 1.1` — HTTP/1.0 closes by default.
2. Forgetting `proxy_set_header Connection ""` — nginx forwards the client's
   `Connection: close`, which tells the upstream to close.

If your upstream keepalive "isn't working," it's almost always one of those two.

---

## 7. Headers and the trust boundary

```nginx
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  THE TRUST-BOUNDARY PROBLEM                                           │
  │                                                                       │
  │  $remote_addr = the TCP peer = the CLIENT as nginx sees it.           │
  │                 (behind another proxy, this is the PROXY's IP.)       │
  │                                                                       │
  │  X-Forwarded-For = a comma list, appended by each hop:                │
  │       client, proxy1, proxy2, ...                                     │
  │                                                                       │
  │  ✗ DANGER: a client can SET X-Forwarded-For itself.                   │
  │            If your app blindly trusts the first value, a client       │
  │            spoofs its IP and evades per-IP rate limits!               │
  │                                                                       │
  │  ✓ RIGHT: trust only the LAST hop you control. nginx appends the      │
  │           real $remote_addr, so the RIGHTMOST entry is trustworthy    │
  │           (given nginx is the last hop before your app).              │
  └──────────────────────────────────────────────────────────────────────┘
```

**In this project:** DRF's `REMOTE_ADDR` will be the nginx pod's IP, not the real
client. For per-user throttling that's fine (it keys on the JWT `sub`, not IP). If you
ever key a limit on client IP, you must configure Django to read `X-Forwarded-For`
**correctly** — taking the last trusted hop, not the first spoofable one. A common bug:
`USE_X_FORWARDED_HOST` / `SECURE_PROXY_SSL_HEADER` set wrong in Django makes it either
ignore the header (rate-limit everyone by proxy IP) or trust a spoofable value
(rate-limit nobody).

---

## 8. Worked example: `/api` → Django

```nginx
upstream expense_api {
    server expense-api.default.svc.cluster.local:8000;
    keepalive 16;
}

server {
    listen 443 ssl;
    server_name api.example.com;

    ssl_certificate     /etc/tls/tls.crt;      # fullchain (leaf + intermediate)
    ssl_certificate_key /etc/tls/tls.key;

    # rate-limit zone (see rate-limiting.md)
    limit_req_zone $binary_remote_addr zone=api_perip:10m rate=20r/s;

    location /api/ {
        limit_req zone=api_perip burst=40 nodelay;

        proxy_pass http://expense_api;         # NO trailing slash → pass /api/... through
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 3s;
        proxy_read_timeout    30s;
        proxy_send_timeout    30s;

        proxy_next_upstream error timeout http_502 http_503 http_504;
    }
}
```

### Debugging with `proxy_next_upstream`

When one upstream errors, nginx can **retry** the next one:

```nginx
proxy_next_upstream error timeout http_502 http_503 http_504;
```

**The safety rule:** only retry **idempotent** requests, or you risk double-applying a
POST. `proxy_next_upstream` by default does **not** retry non-idempotent methods unless
you add `non_idempotent` (don't). An expense POST that hits a flaky backend should
return an error, not silently create two expenses.

**Diagnostic checklist when "nginx returns 502/504":**

```
  502 Bad Gateway       → upstream refused/reset the connection
                          check: is the pod up? right port? listening on 0.0.0.0?
  504 Gateway Timeout   → upstream didn't respond in proxy_read_timeout
                          check: is the query slow? the whole pool saturated?
  connection refused    → nothing on that host:port (Service selector wrong?)
  upstream timed out    → see 504
```

See also [`ingress-in-k3s.md`](ingress-in-k3s.md) for how to read the *rendered*
config the ingress controller generated from your annotations.

---

## 9. Interview angle

- **"Reverse vs forward proxy?"** — who it represents: client (forward) vs servers
  (reverse). Egress filtering vs ingress control.
- **"What does the trailing slash on proxy_pass do?"** — replaces the matched location
  prefix vs passes it through. The classic "why is my backend 404ing" question.
- **"Why is X-Forwarded-For dangerous?"** — client-settable; trust only the last hop you
  control.
- **"Difference between connect/read/send timeout?"** — connection establishment vs
  upstream stalling on reads vs on writes; all but connect are inactivity timers.
- **"How do you avoid a double POST on retry?"** — don't retry non-idempotent requests;
  `proxy_next_upstream` excludes them by default.

---

## 10. How this shows up here

- The `/api` → DRF routing lives in the Ingress annotations, which render to a
  `proxy_pass` block like §8.
- Upstream keepalive cuts handshake overhead to the API pods — worth enabling once
  there's more than a trivial request rate.
- The trust-boundary header problem is real if any limit keys on IP: nginx is the last
  hop, so it must append `X-Forwarded-For` and Django must read it correctly
  ([`rate-limiting.md`](rate-limiting.md), [`../drf-jwt-guide.md`](../drf-jwt-guide.md)).
- `proxy_read_timeout` must accommodate the slowest legitimate report — a value to
  record in `design.md`.
