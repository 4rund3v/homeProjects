# NGINX — The Edge

> How the edge of this system actually works: process model, reverse proxying, load
> balancing, rate limiting, caching, security headers, and how it all runs inside k3s
> as ingress-nginx. Written for **L5/L6 interview prep** and as the project's edge
> reference.

> **Where TLS lives:** TLS mechanics — the handshake, cipher suites, certificates,
> PFS — are in [`../tls/`](../tls/). This folder covers what NGINX *does with* TLS
> (terminate it, forward plain HTTP), not how TLS works.

> **Where rate-limiting algorithms live:** the algorithms themselves — fixed window,
> token bucket, GCRA, distributed limiters — are in
> [`../rate-limiting.md`](../rate-limiting.md). [`rate-limiting.md`](rate-limiting.md)
> here is about NGINX's *implementation* only.

## The docs

| File | What it covers | Read when |
|------|----------------|-----------|
| [`architecture.md`](architecture.md) | Master/worker processes, `epoll`, event loop vs threads vs goroutines, config reload with zero dropped connections, upstreams | To answer "why is nginx fast?" |
| [`reverse-proxy.md`](reverse-proxy.md) | Reverse vs forward proxy, `proxy_pass` and the URI-substitution trap, the three timeouts, buffering, upstream keepalive, header rewriting and the trust boundary | Before writing any proxy config |
| [`load-balancing.md`](load-balancing.md) | round-robin, least_conn, ip_hash, hash, consistent hash; sticky sessions and why not here; health checks; zero-downtime rollouts | When you have >1 API replica |
| [`rate-limiting.md`](rate-limiting.md) | `limit_req_zone`, `limit_req` + `burst`/`nodelay`, `limit_conn`, the client-IP key problem, ingress-nginx annotations | Phase 11 — the edge limiter |
| [`ingress-in-k3s.md`](ingress-in-k3s.md) | Ingress/IngressClass CRDs, annotations → nginx.conf, inspecting the rendered config, leader election, EndpointSlices, the `allow-snippet-annotations` escalation vector | Debugging "why isn't my route working" |
| [`caching-and-gzip.md`](caching-and-gzip.md) | `proxy_cache`, `Cache-Control`/`Vary` (the `Vary: Authorization` trap), stale-while-revalidate, SPA `try_files`, gzip/Brotli | Serving the UI, or tempted to cache an API |
| [`security-and-headers.md`](security-and-headers.md) | CSP, HSTS (and why preload is one-way), `client_max_body_size`, timeouts, `server_tokens`, log format for correlation | Before you expose anything |
| [`tuning-and-observability.md`](tuning-and-observability.md) | `worker_processes`, `worker_connections`, fd limits and the math, `sendfile`/`tcp_nodelay`, `stub_status`, the exporter, what each metric means | When it's slow, or you're setting alerts |

## Suggested reading order

**If you have an interview tomorrow:** `architecture` → `reverse-proxy` →
`load-balancing` → `rate-limiting`. Those four cover most nginx questions.

**If you are building this edge:** `ingress-in-k3s` (get a route working) →
`reverse-proxy` (get it right) → `rate-limiting` + `security-and-headers` (harden it)
→ `tuning-and-observability` (watch it).

**Reference-as-needed:** caching, tuning.

## The one-paragraph mental model

NGINX is a small **master process** that reads a config and spawns **worker processes**;
each worker runs a single-threaded **event loop** (`epoll`) over thousands of
non-blocking sockets, which is why it handles enormous concurrency in little memory —
there are no per-connection threads to schedule or stacks to allocate. As a **reverse
proxy** it accepts a client connection, applies edge policy (TLS, rate limits, headers,
caching), opens or reuses an **upstream** connection, relays the request, and streams
the response back — load-balancing across upstreams with one of a few algorithms and
dropping failed ones via **health checks**. Everything nginx knows is in its config;
reloading it starts new workers that drain old ones without dropping a connection. Each
doc below is one of those sentences expanded.
