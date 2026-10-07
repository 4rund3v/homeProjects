# Rate Limiter

## What this project exists to solve
Rate limiting is a foundational reliability and security control that every production service needs, yet its algorithm trade-offs are rarely taught explicitly. This project bridges the gap between pure algorithm study and real middleware design: first build two well-understood limiters from scratch as a testable library, then wire them into a live HTTP server. Placing it at Phase 1.5 — after algorithms and before advanced services — ensures the concurrency and testing habits from `go-fundamentals` are exercised on a non-trivial concurrent data structure before the pattern recurs in `raft-adv` and `telemetry-hub`.

## Success criteria / completion metrics
- `Limiter` interface defined; token bucket and sliding window counter each satisfy it.
- Both implementations pass `go test -race ./...` with zero data races under high goroutine concurrency.
- Property tests confirm: token bucket never grants more than `capacity` tokens in any window; sliding window never exceeds `limit` requests in any full window.
- Written analysis (in a `docs/` file) explaining when sliding window over- or under-counts compared to token bucket, with a concrete example.
- go-http-server middleware returns HTTP 429 with a correct `Retry-After` header; integration tests cover burst admission, steady-state pass-through, and per-key isolation (two keys do not share quota).
- Benchmark comparing token bucket vs. sliding window throughput under high concurrency; results summarized in `docs/benchmarks.md`.
- (Optional) Redis-backed limiter passes the same interface tests; measured latency overhead vs. in-process limiter documented.

## Prerequisites and dependencies
- `go-fundamentals`: goroutines, channels, `sync` primitives, race detector, table-driven tests, benchmarks.
- `go-http-server`: middleware chain, `http.Handler` composition, `httptest` integration tests.
- (Milestone 4 only) `redis-cache`: Redis connection setup, go-redis client, atomic Lua script execution.

## Tools, libraries, and runtime
- Go stdlib: `sync`, `sync/atomic`, `time`, `net/http`, `testing`.
- `go test -race` and `go test -bench` for correctness and performance validation.
- No external dependency for milestones 1–3; `github.com/redis/go-redis/v9` for optional milestone 4.
- Local Redis instance (Docker) only for milestone 4.

## Learning objectives (skills practiced)
- Modeling a rate limiting algorithm as a testable Go interface with distinct implementations.
- Safe concurrent access to per-key state using `sync.Map`; understanding why a global mutex would serialize all requests.
- Token bucket: lazy refill on access vs. background ticker; capacity vs. rate distinction.
- Sliding window counter: boundary arithmetic, why requests near a window edge can be counted in two windows.
- Writing property-based and invariant tests that hold under arbitrary timing and goroutine scheduling.
- HTTP middleware composition: where in the chain a limiter sits and why ordering matters.
- `Retry-After` semantics: seconds-form vs. HTTP-date form; what clients are expected to do with it.
- Benchmark methodology: establish baseline, vary concurrency, interpret ns/op and allocs/op, avoid microbenchmark traps.

## Architecture / design note
Suggested layout:
```
ratelimit/
  limiter.go          ← Limiter interface and shared types
  tokenbucket.go
  tokenbucket_test.go
  slidingwindow.go
  slidingwindow_test.go
  store.go            ← per-key map wrapper (sync.Map)
  store_test.go
  redis/              ← optional; milestone 4 only
    redislimiter.go
middleware/
  ratelimit.go        ← http.Handler adapter; key extractor func
  ratelimit_test.go   ← httptest integration tests
docs/
  algorithm-comparison.md
  benchmarks.md
```
Key design decisions to make explicitly:
- Define the `Limiter` interface before any implementation so tests target the interface.
- The key extractor (IP vs. `X-API-Key` header) is a function parameter; the middleware does not hard-code extraction logic.
- Do not share a `Limiter` instance across keys; the store wraps a `sync.Map[string, Limiter]` and constructs per-key instances lazily.

## Test strategy
- **Property tests** (milestones 1–2): in a tight loop of N goroutines each making M `Allow()` calls, assert total admitted ≤ expected quota within the measurement window. Run with `-race`.
- **Unit tests**: verify refill math at boundary conditions (empty bucket, full bucket, partial refill).
- **Integration tests** (milestone 3): use `httptest.NewServer` against the middleware-wrapped handler; fire bursts above and below the limit; assert 429 vs. 200 counts and `Retry-After` header presence.
- **Benchmarks** (milestone 3): `BenchmarkTokenBucket` and `BenchmarkSlidingWindow` under 1, 4, and 16 concurrent goroutines; record and commit results to `docs/benchmarks.md`.
- **Redis integration tests** (milestone 4): require a real Redis connection; skip with `t.Skip` if `REDIS_ADDR` env var is unset so CI does not break without Redis.

## Documentation checklist
- `README.md`: build, test, and benchmark commands; how to plug the middleware into go-http-server.
- `docs/algorithm-comparison.md`: token bucket vs. sliding window semantics, burst behavior, over/under-counting examples.
- `docs/benchmarks.md`: benchmark results table, concurrency levels tested, interpretation notes.
- (Milestone 4) `docs/distributed-limiter.md`: architecture, consistency trade-offs, measured latency overhead.

## API contract
No HTTP API. The library exposes:
```
type Limiter interface {
    Allow() bool
    // Returns the duration the caller should wait before retrying.
    RetryAfter() time.Duration
}

// Middleware constructor; keyFn extracts the rate-limit key from a request.
func Middleware(store *Store, keyFn func(*http.Request) string, lim LimiterFactory) func(http.Handler) http.Handler
```
HTTP behavior: `429 Too Many Requests` with `Retry-After: <seconds>` when `Allow()` returns false.

## UI / status surfaces
None. CLI output only via test runner and benchmark output.

## Security boundaries to think about
- Rate limiting is a **defense-in-depth** measure, not a primary authentication or authorization control; document this explicitly — a sophisticated client can still exhaust quotas or spoof keys.
- IP-based limiting is bypassable via proxies or shared NAT; API-key-based limiting is more precise but requires an auth layer to issue and validate keys.
- In-process limiters are per-instance: horizontal scaling without a shared backend (Redis) means each replica enforces its own quota independently, effectively multiplying the allowed rate by the replica count.
- `sync.Map` lazy construction can create a memory-growth vector if the key space is unbounded (e.g., arbitrary IP addresses); bound the key space or add a periodic eviction strategy.
- Avoid logging request bodies or keys that could contain credentials.

## Profiling plan
Benchmark the in-process limiter using `go test -bench=. -benchmem -count=5` at 1, 4, and 16 goroutines. Compare ns/op and allocs/op between token bucket and sliding window. Profile with `go test -cpuprofile` only if the benchmark reveals an unexpected hot path. Do not optimize based on a single benchmark run — use `-count=5` and check for variance.

## How this project fits into the curriculum
Sits between `go-fundamentals` (algorithms, concurrency, tests) and the advanced service projects. It is the first project to produce a **reusable Go library** rather than a standalone service, establishing the `internal/` package discipline used later. The middleware pattern it delivers is directly consumed by `go-http-server`. The optional Redis milestone bridges to `redis-cache` and previews the distributed state concerns central to `raft-adv`.

## Suggested milestone walkthrough
1. **Define the interface.** Write `Limiter` interface and a stub `TokenBucket` struct; add a failing property test; make the test pass with a correct implementation; run `-race`.
2. **Sliding window.** Implement `SlidingWindowCounter`; make it satisfy the same interface tests; write a comparison note identifying at least one scenario where the two algorithms differ on admission.
3. **Per-key store.** Wrap both implementations in a `sync.Map`-backed `Store`; confirm per-key isolation with a test that shows two keys do not share quota.
4. **HTTP middleware.** Write the `Middleware` adapter; plug into go-http-server; add integration tests; verify `Retry-After` header; run benchmarks and commit results.
5. **(Optional) Redis limiter.** Implement `RedisLimiter` using an atomic Lua script or `INCR`+`EXPIRE`; run the same interface tests; measure and document latency overhead vs. in-process.

## Reference notes and resources
- Cloudflare blog: "How we built rate limiting" (sliding window log vs. counter trade-offs).
- Go `sync.Map` documentation and source — understand when it outperforms a mutex-protected map.
- RFC 6585 §4: HTTP 429 Too Many Requests and `Retry-After` header semantics.
- Go testing documentation: `-race`, `-bench`, `-benchmem`, `-count` flags.
- `github.com/redis/go-redis/v9` documentation for Lua script execution (milestone 4).
