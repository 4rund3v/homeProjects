# 04 — Session affinity, and when round-robin is wrong

## Round-robin is the default. It is often wrong.

Round-robin (the L4 default, and NGINX's default LB method) sends request N to backend N mod M. It is *fair* but *stateless*. Two problems in real services:

1. **Caches go cold.** If the app caches per-pod (in-memory cache of products), round-robin means every pod misses every M-th request.
2. **Connections are expensive.** Opening a new DB connection or TLS session per request is wasteful. Reusing an existing connection to a "sticky" backend is much cheaper.

## L4 affinity: by client IP

```
service.spec.sessionAffinity: ClientIP
service.spec.sessionAffinityConfig.clientIP.timeoutSeconds: 10800
```

All connections from one source IP go to the same pod. Simple, but breaks for mobile users behind NAT (all one IP → all one pod → hot spot) and for users whose IP changes mid-session (affinity lost).

## L7 affinity: by cookie

```
nginx.ingress.kubernetes.io/affinity: "cookie"
nginx.ingress.kubernetes.io/affinity-mode: "balanced"
nginx.ingress.kubernetes.io/session-cookie-name: "shop-route"
nginx.ingress.kubernetes.io/session-cookie-max-age: "3600"
```

NGINX sets a cookie on the first response, then routes all requests with that cookie to the same backend. Works across IP changes, works behind NAT. The cookie *is* the affinity.

`affinity-mode: balanced` means "redistribute if the backend is unhealthy or overloaded." `persistent` means "never move the user." For most services, balanced is right.

## When affinity is actively harmful

- **Uneven load.** One whale user (a big script hammering one endpoint) pins to one pod. That pod's p99 dies while the others idle. Observable: `sum by (pod) (rate(http_request_duration_seconds_count[5m]))` shows one pod at 3× the others.
- **Rolling updates.** With sticky sessions, an old pod cannot drain until its cookies expire. A rolling update stalls.
- **Memory state.** Affinity encourages teams to keep state in the pod. That is the road to "we cannot restart pod X."

## The senior-engineer heuristic

Default to round-robin (stateless, even load). Add affinity only when a *specific measurable problem* says so: cache hit ratio, connection reuse rate, or a session-based protocol (WebSocket, legacy login flow).

If you add affinity, you must then watch:
- Per-pod RPS (even-ness).
- Per-pod p95 (the whale-user signature).
- Rolling-update time (drain stall).

## WebSocket: affinity is mandatory

A WebSocket is one long-lived TCP connection. It pins to one backend for its lifetime — not by cookie, by the connection itself. NGINX handles this with `proxy_read_timeout` and an upstream that does not close idle connections. The lab in `labs/session-affinity.md` does not cover WebSocket, but the principle is the same: connection-level, not request-level.
