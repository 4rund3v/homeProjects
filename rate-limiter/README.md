# Rate Limiter

**Goal:** Implement token bucket and sliding window counter algorithms as a clean Go library, then integrate them as HTTP middleware in go-http-server.

**Scope:** Token bucket algorithm, sliding window counter algorithm, per-key limiting (by IP or API key), `sync.Map`-based concurrent state, go-http-server middleware adapter, 429 responses with `Retry-After`, property and integration tests, benchmarks; optional Redis-backed distributed limiter.

**Out of scope:** Leaky bucket or fixed window algorithms, deployment-time configuration hot-reload, admin API to manage limits, non-Go clients.

**Learning focus:** Rate limiting algorithm trade-offs (burst vs. smooth), concurrent map access patterns, middleware design, HTTP 429 semantics, benchmark-driven comparison, defense-in-depth thinking.

**Depends on:** `go-fundamentals`; `go-http-server` for middleware integration; `redis-cache` for optional milestone 4.

## Milestones
- [ ] Define the `Limiter` interface and implement token bucket; verify correctness under concurrent access with `go test -race` and property tests.
- [ ] Implement sliding window counter; document when each algorithm over- or under-counts relative to the other.
- [ ] Wrap both algorithms as go-http-server middleware; return 429 with `Retry-After`; write integration tests covering burst and steady-state traffic.
- [ ] (Optional) Redis-backed distributed limiter sharing state across multiple in-process instances; compare consistency and latency with the in-process limiter.
