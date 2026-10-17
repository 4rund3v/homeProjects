# Security and Headers

> The edge is the last line of defense before traffic reaches your app. It can't
> authenticate users, but it *can* reject requests cheaply, add protective headers, and
> prevent the classes of bugs that live at the network edge.

> TLS *mechanics* — the handshake, cipher suites, certificates — are in
> [`../tls/`](../tls/). This doc covers what NGINX does to *enforce* edge policy
> around TLS.

---

## 1. The posture

```
  ┌──────────────────────────────────────────────────────────────┐
  │  The edge is NOT the only defense — but it's the cheapest one.│
  │                                                                │
  │  • Per-request work here is ~1-5 µs vs ~1 ms in Python.       │
  │  • Rejection at the edge costs the client one RTT and nothing │
  │    else.                                                       │
  │                                                                │
  │  • What you CAN'T do at the edge: authenticate a user, check  │
  │    permissions, validate the request body semantically.        │
  │  • What you CAN: size limits, timeouts, header policy, TLS     │
  │    negotiation, rate limits, coarse abuse rejection.           │
  └──────────────────────────────────────────────────────────────┘
```

Defense in depth: the edge stops the easy stuff, the app stops the semantically bad
stuff. Neither substitutes for the other.

---

## 2. Security headers

Set these on **every** response, from the edge, so a misconfigured app can't omit them:

```nginx
server {
    # Content Security Policy — the modern XSS/CSP story
    add_header Content-Security-Policy
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; object-src 'none'; "
        "upgrade-insecure-requests" always;

    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy
        "camera=(), microphone=(), geolocation=(), payment=(), usb=(), magnetometer=()" always;

    # Note: for a CSP with 'self' the value changes as you add origins
    # (fonts, CDN for the UI, Datadog's SDK, etc.)
}
```

### The headers and what they actually do

| Header | Purpose |
|--------|---------|
| `Content-Security-Policy` | The modern XSS defense. Restricts which origins scripts/styles/imgs load from. `'self'` is the safe start. |
| `X-Content-Type-Options: nosniff` | Prevent MIME-sniffing; the browser uses the declared Content-Type. Blocks `text/html` served as `text/plain` from executing. |
| `X-Frame-Options: DENY` | Prevents clickjacking via framing. Modern equivalent is `frame-ancestors` in CSP. |
| `Referrer-Policy` | Controls what the Referer header leaks. `strict-origin-when-cross-origin` is the safe modern default. |
| `Permissions-Policy` | Disables browser features (camera, mic, geolocation) you don't use. |
| `Strict-Transport-Security` | Force HTTPS — see §2.1 for why preload is dangerous. |
| `Cross-Origin-Embedder-Policy` / `Cross-Origin-Opener-Policy` | Isolation for advanced CSP `trusted-types` scenarios; skip for this project. |

**`always` on `add_header`** — applies the header on all responses, including 4xx/5xx
from the proxy. Without it, an error path may lose the headers.

### CSP gotchas

- **`'unsafe-inline'` is a hole.** It lets any inline `<script>` or `style=""` execute.
  The React SPA can usually avoid it by using separate files; if it can't, the CSP is
  much weaker than you think.
- **`default-src` fallback.** Anything not explicitly listed falls back to
  `default-src`. Set it to `'self'` and add exceptions as you hit them.
- **Third-party scripts (Datadog's RUM SDK, sentry, etc.)** require you to add their
  domains to `script-src`. Prefer hash-based (`sha256-...`) or nonce-based policies for
  anything inline.

### 2.1 HSTS and why preload is one-way

```nginx
add_header Strict-Transport-Security
    "max-age=15552000; includeSubDomains; preload" always;
```

```
  ┌────────────────────────────────────────────────────────────────┐
  │  max-age=15552000        → browsers trust this for 6 months      │
  │  includeSubDomains       → applies to all subdomains             │
  │  preload                 → declares you WANT to be on the       │
  │                              HSTS preload list at preload.hsts   │
  │                                                                  │
  │  WHY PRELOAD IS DANGEROUS:                                       │
  │  • Once preloaded, browsers ship HSTS for you forever.           │
  │  • REMOVAL is possible but slow, and you can't undo accidental   │
  │    preload of a *subdomain you own but no longer control*.       │
  │  • A leaked TLS cert is unrecoverable once preloaded.            │
  │  • The submission must be made from every subdomain you own.     │
  │                                                                  │
  │  RECOMMENDATION: skip preload for this project.                  │
  │  Set HSTS with max-age and includeSubDomains, but leave          │
  │  "preload" OFF.                                                   │
  └────────────────────────────────────────────────────────────────┘
```

---

## 3. Request-size and time limits

### `client_max_body_size` — the 413 you'll hit

```nginx
client_max_body_size 1m;   # default 1m; anything larger → 413 Request Entity Too Large
```

```
  ┌──────────────────────────────────────────────────────────────┐
  │  THE COMMON BUG:                                             │
  │    A client POSTs a payload > 1 MB → nginx returns 413       │
  │    with no log line the client can diagnose.                 │
  │    The app never sees the request.                            │
  │                                                               │
  │  FIX: set a reasonable limit (e.g. 5m for file uploads) AND  │
  │  log 413s with an error-level message.                        │
  │                                                               │
  │  For ingress-nginx:                                            │
  │    nginx.ingress.kubernetes.io/proxy-body-size: "5m"         │
  └──────────────────────────────────────────────────────────────┘
```

### Time limits

```nginx
client_body_timeout  30s;   # time to receive the whole request body
client_header_timeout 30s;  # time to receive the whole request headers
send_timeout          60s;  # time between successive WRITES to the client
```

**Why these matter:** a client that opens a connection and sends nothing ties up a
worker for the whole timeout. Slowloris-style attacks rely on exactly this. Keep them
tight enough to reject slow clients, loose enough that slow clients on mobile networks
don't trip.

---

## 4. Hide the version

```nginx
server_tokens off;
```

**Effect:** `Server: nginx` instead of `Server: nginx/1.24.0 (Ubuntu)`.

Real mitigation is limited — the version is guessable from behavior. But it's a cheap
"don't hand an attacker the target list" move. Zero cost.

---

## 5. Access log format for correlation

The correlation ID is how a request threads through nginx → app → Kafka → consumer.
Your nginx log must include the fields that make tracing possible.

```nginx
log_format escape_json escape=json escape=csv escape=always escape=unicode
    '{'
    '"time":"$time_iso8601",'
    '"remote_addr":"$remote_addr",'
    '"request_id":"$req_id",'              # nginx $req_id (or a custom UUID)
    '"method":"$request_method",'
    '"path":"$request_uri",'
    '"status":$status,'
    '"body_bytes":$body_bytes_sent,'
    '"upstream_status":"$upstream_status",'
    '"request_time":$request_time,'
    '"upstream_response_time":"$upstream_response_time",'
    '"http_referer":"$http_referer",'
    '"http_user_agent":"$http_user_agent"'
    '}';

access_log /var/log/nginx/access.log escape_json;
```

```
  ┌───────────────────────────────────────────────────────────────┐
  │  CORRELATION ID FLOW                                          │
  │                                                                │
  │   Client ──[X-Request-ID: abc]──► nginx                        │
  │                              │   (or nginx generates $req_id) │
  │                              │                                 │
  │                              │──[X-Request-ID: abc]──► app     │
  │                              │         │                       │
  │                              │         │──[trace_id: abc]──► DB│
  │                              │         │                       │
  │                              │         │         Kafka event   │
  │                              │         │        {event_id, ...}│
  │                              │         │                       │
  │  The same "abc" should appear in every log line along this     │
  │  path. That's the whole point of the correlation ID.          │
  └───────────────────────────────────────────────────────────────┘
```

**The `map` trick to prefer a client-supplied ID:**

```nginx
map $http_x_request_id $req_id {
    default   $http_x_request_id;     # use if the client provided one
    ""        $request_id;            # else use nginx's generated one
}
```

---

## 6. SSRF and abuse at the proxy

```
  ┌──────────────────────────────────────────────────────────────┐
  │  Server-Side Request Forgery at the edge                     │
  │                                                                │
  │  If your nginx is configured to proxy to an internal service  │
  │  (e.g. a service registry or admin API), and any user control │
  │  leaks into proxy_pass or host resolution, they can access    │
  │  the internal network as you.                                  │
  │                                                                │
  │  Typical vector: an "image proxy" endpoint that fetches an    │
  │  arbitrary URL. The attacker points it at                     │
  │  http://169.254.169.254/latest/meta-data (cloud metadata).   │
  │                                                                │
  │  Mitigation: allow-list the destinations nginx can proxy to.  │
  │  Never accept a user-supplied URL for a server-side fetch.    │
  └──────────────────────────────────────────────────────────────┘
```

Not directly relevant to the API in this project (no user-supplied fetches), but the
pattern applies to any future "proxy" endpoint you add.

---

## 7. Interview angle

- **"What security headers do you set at the edge?"** — CSP, X-Content-Type-Options,
  X-Frame-Options, Referrer-Policy, Permissions-Policy, HSTS, `server_tokens off`,
  with `always` on `add_header` to cover error paths.
- **"Why is HSTS preload dangerous?"** — once preloaded, you can't easily undo it.
  Prefer max-age + includeSubDomains without preload.
- **"What does `client_max_body_size` catch?"** — oversized bodies, returned as 413
  before they reach the app; the classic "app never sees the request" bug.
- **"How do you correlate requests across the stack?"** — a request ID, either client-
  supplied or nginx-generated, propagated as a header to the upstream and into app
  logs.

---

## 8. How this shows up here

- Every response gets the §2 headers from the ingress.
- `client_max_body_size` = a value that accommodates legitimate API payloads; log the
  413s.
- The log format feeds the correlation ID that threads through DRF, the outbox, and
  the consumer ([`../observability.md`](../observability.md)).
- HSTS without preload; TLS termination handled separately
  ([`../tls/this-project-topology.md`](../tls/this-project-topology.md)).
