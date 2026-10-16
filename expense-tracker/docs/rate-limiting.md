# Rate Limiting — Algorithms, Trade-offs, and Production Practice

> The complete reference: **every core algorithm** (fixed window, sliding window log,
> sliding window counter, token bucket, leaky bucket, GCRA), distributed rate limiting,
> where limiters live in the stack, failure modes, and how the layers compose in this
> project. NGINX's specific implementation is in
> [`nginx/rate-limiting.md`](nginx/rate-limiting.md); DRF's is in
> [`drf-jwt-guide.md`](drf-jwt-guide.md) §6.

---

## 1. Why rate limit at all

Four distinct jobs, often conflated — knowing which one you need shapes the design:

| Job | What it protects from | Failure it prevents |
|-----|----------------------|---------------------|
| **Abuse control** | credential stuffing, scraping, brute-force login | account takeover |
| **Fairness** | one noisy tenant starving others | noisy-neighbor disputes |
| **Load protection** | traffic spikes your backend can't absorb | cascading overload / outage |
| **Cost control** | paid APIs, third-party quota exhaustion | surprise bills |

A limit designed for abuse (strict, per-user, login-only) looks nothing like one
designed for load protection (generous, global, everywhere). Name the job first.

**The three design axes:**

1. **Key** — per-IP? per-user? per-API-key? per-endpoint? (login vs read vs write)
2. **Scope** — local (per process) or distributed (shared state)?
3. **Response** — reject with 429, queue/shed, or degrade?

---

## 2. The core algorithms

### 2.1 Fixed window counter

**Mechanism:** divide time into fixed windows (e.g. 00:00–00:60). Keep one counter per
(key, window). Increment on each request; reject when the counter ≥ limit. Reset when
the window rolls.

```
Window:      |---- w1 ----|---- w2 ----|---- w3 ----|
Limit: 5

w1 requests:  ●●●●●  →  5th allowed, 6th rejected
w2 requests:  ●●     →  counter starts fresh at 0

THE BOUNDARY PROBLEM:
             ...●●●●●|●●●●●...
                   ↑
        5 requests at end of w1 + 5 at start of w2
        = 10 requests in ~2 seconds — double the intended rate
```

- **Cost:** O(1) time, O(keys) memory. The cheapest algorithm.
- **Pros:** trivial to implement, trivial to reason about, trivial to shard.
- **Cons:** **burst-at-boundary** — up to 2× the intended rate can pass in a window
  straddling the boundary (diagram above). Exact per-window, inexact per-any-actual-
  sliding-period.
- **Use:** coarse abuse control where 2× bursts are tolerable; cheap first line.

### 2.2 Sliding window log

**Mechanism:** keep a **timestamped log** of every accepted request per key. On a new
request, drop timestamps older than the window, count the rest, allow if count < limit.

```
Key: user:42   Limit: 5 per 60s        now = t
                           ┌─ window start (t-60s)
                           ▼
   t-90s   t-70s   t-50s   t-40s   t-20s   t-5s    NEW REQUEST at t
   ──✂ dropped ✂──  |    ●      ●      ●      ●   → 4 in window → ALLOW, log t
```

- **Cost:** O(n) memory per key (n = requests in window), O(n) or O(log n) prune.
- **Pros:** **exact**. No boundary problem — the window truly slides.
- **Cons:** memory scales with traffic, not with key count. Expensive at scale.
- **Use:** low-traffic, high-precision needs (billing-grade enforcement); rarely the
  default at scale.

### 2.3 Sliding window counter (the hybrid)

**Mechanism:** approximate a sliding window from **two adjacent fixed windows**,
weighted by how far we are into the current one:

```
estimated =  count(prev window) × (1 - elapsed/window)  +  count(curr window)

Example: limit 5/60s, now 15s into the current window
         prev count = 4, curr count = 3
         estimate  = 4 × (1 - 15/60) + 3  = 4 × 0.75 + 3  = 6  →  REJECT
```

- **Cost:** O(1) — just two counters and arithmetic.
- **Pros:** near-exact, fixed-window cheap, kills most of the boundary burst.
- **Cons:** an approximation (err conservative by tuning); assumes roughly even
  distribution within a window.
- **Use:** the default answer for distributed limiters — Cloudflare's famous blog post
  popularized exactly this.

### 2.4 Token bucket

**Mechanism:** the key has a bucket holding up to `capacity` tokens. Tokens refill at
`refill_rate` (tokens/sec) up to capacity. Each request consumes one token; no token →
reject (or wait).

```
Bucket: capacity 5, refill 1/sec

t=0:   █████ 5 tokens — burst of 5 allowed instantly
t=0.5: request●request●request → 2 left
t=1:   ███ refill tops it back to 3
t=5:   █████ idle period → full again → another burst of 5 allowed

  Allows BURSTS up to capacity, while bounding the AVERAGE rate to refill_rate.
```

- **Cost:** O(1) — one timestamp + one token count (see GCRA, §2.6).
- **Pros:** the only mainstream algorithm that models **bursts** explicitly. Sustained
  rate = `refill_rate`; instantaneous = `capacity`. Matches real traffic and real
  products (AWS API limits are token buckets).
- **Cons:** two parameters to reason about; bursts are only bounded to `capacity`, so
  downstream must survive a full-bucket burst.
- **Use:** product-facing API quotas — "100 requests/min, burst 20".

### 2.5 Leaky bucket

**Mechanism:** requests enter a **queue** (the bucket); they drain at a **constant**
rate. Queue full → reject. Output is perfectly smooth regardless of input burstiness.

```
  bursty input              bucket (queue, cap 5)      smooth output
                              ┌─────────────┐
  ●●●●●●●●●●●●● ──────────►  │ ●●●●● ──►  │ ──────────►  ●  ●  ●  ●
                              └─────────────┘            (constant rate,
                              overflow = REJECT (429)     e.g. 1/sec)
```

- **Cost:** O(queue size).
- **Pros:** output rate is **exactly** constant — ideal when the thing downstream is
  rate-sensitive (a fragile third-party API, a payment processor).
- **Cons:** adds **latency** (requests wait in the queue); burstiness is flattened,
  not absorbed-and-passed-through like token bucket.
- **Use:** shaping traffic toward a fragile/slow dependency. **NGINX's `limit_req` is
  a leaky bucket** (with `burst` as the queue size — see below).
- **Token vs leaky, in one line:** token bucket answers "*when* may I send?";
  leaky bucket answers "*when* do I forward what you sent."

### 2.6 GCRA (Generic Cell Rate Algorithm)

The elegant production algorithm behind many "token bucket" implementations (Redis
`CELL` module, Discord's limiter). Instead of storing tokens, store one timestamp:
the **theoretical arrival time (TAT)** of the next allowed request.

```
TAT semantics:  each accepted request pushes TAT forward by 1/refill_rate.
                A new request at time t is allowed if  t + capacity/refill ≥ TAT
                (i.e. "even if I run full-bucket from now, I'd not overtake").

State per key: ONE timestamp. Same behavior as token bucket, O(1), race-friendly
(single compare-and-set), no queue.
```

- **Use:** when you want token-bucket semantics with the least possible shared state —
  the go-to for Redis-based distributed limiters.

### 2.7 The comparison table (memorize this)

| Algorithm | Memory/key | Exact? | Burst behavior | Classic use |
|-----------|-----------|--------|----------------|-------------|
| Fixed window | 1 counter | per-window only | up to 2× at boundary | cheap abuse control |
| Sliding log | n timestamps | **exact** | none (true window) | billing precision |
| Sliding counter | 2 counters | ~exact | tiny residue | **distributed default** (Cloudflare) |
| Token bucket | 1 counter + 1 ts | rate-avg exact | bursts ≤ capacity | **API quotas** (AWS-style) |
| Leaky bucket | queue | output-rate exact | smoothed away | protect fragile downstream (NGINX) |
| GCRA | 1 timestamp | = token bucket | bursts ≤ capacity | Redis/production limiters |

---

## 3. Distributed rate limiting

One process can count in memory. **Multiple replicas cannot** — the state must be
shared or the effective limit becomes `limit × replicas`.

```
                    ┌────────────┐        ┌────────────┐
                    │  app pod 1 │        │  app pod 2 │
                    └─────┬──────┘        └──────┬─────┘
                          │    INCR / EVAL        │
                          ▼                       ▼
                    ┌─────────────────────────────────┐
                    │   shared store (Redis)           │
                    │   key → counter / TAT / ZSET     │
                    └─────────────────────────────────┘
```

**The naive Redis attempt and its race:**

```
1. GET count            → 4          (limit 5)
2. (another pod does the same GET → also sees 4)
3. INCR count           → 5          ✓ allowed
4. (other pod INCRs     → 6          ✗ should have been rejected — RACE)
```

**Fixes, in order of correctness:**

1. **Atomic Lua script** (`INCR` + expiry + compare in one atomic step) — the standard.
2. **GCRA via a single compare-and-set** — one round trip, atomic by design.
3. **Sorted set (ZSET)** sliding log — `ZADD` timestamps, `ZREMRANGEBYSCORE` the old,
   `ZCARD` the count — all in one Lua script. Exact, heavier.

**The latency and availability tax:** every request now round-trips to Redis — that's
1–2 ms added and, worse, a **new dependency on the critical path**. Two mitigations:

- **Local pre-filter:** keep a cheap local approximation (e.g. local fixed window at
  ~110% of the global limit) and only consult Redis on borderline cases.
- **Async aggregation:** each pod counts locally, pods sync counters periodically
  (eventually consistent). Exactness is traded for zero critical-path dependency —
  right for fairness, wrong for billing.

**Fail-open vs fail-closed:** when Redis is down, do you allow (fail-open) or reject
(fail-closed)? For abuse control → **fail-open** (the limiter dying shouldn't take the
site down). For billing-grade enforcement → fail-closed. Decide explicitly; write it
in [`design.md`](design.md).

---

## 4. Client behavior — the failure modes limiters create

A limiter changes what clients do, and naive clients make limiters *worse*:

- **Retry storms:** 429 → client retries immediately → the retry IS the new load. The
  fix is mandatory: honor **`Retry-After`**, and add **jitter** so synchronized
  clients don't retry in a herd.
- **Thundering herd at window boundary:** every client that got limited at 12:00:59
  retries at 12:01:00 — a synchronized spike. Jittered retry timing breaks the sync.
- **Status semantics:** 429 means "you're sending too much" (client's fault, back
  off); 503 means "I'm overloaded" (server's fault, maybe retry elsewhere). Never use
  them interchangeably.

**Standard response headers:**

```
HTTP/1.1 429 Too Many Requests
Retry-After: 30                          ← seconds until a retry can succeed
RateLimit-Limit: 100                     ← the IETF draft headers
RateLimit-Remaining: 0
RateLimit-Reset: 27
```

(Legacy `X-RateLimit-*` variants are everywhere; support reading both.)

---

## 5. Where limiters live — the layered answer

No single layer sees the full picture, so production systems stack them:

```
┌───────────────────────────────────────────────────────────────┐
│ L1  EDGE / NGINX        per-IP leaky bucket (coarse, dumb,    │
│                         survives anything upstream throws)     │
├───────────────────────────────────────────────────────────────┤
│ L2  APP / DRF           per-user semantic throttles            │
│                         (login stricter than reads; per-user   │
│                         because JWT gives us identity)         │
├───────────────────────────────────────────────────────────────┤
│ L3  SERVICE / DEPENDENCY per-dependency token bucket           │
│                         (protect the fragile third-party API)  │
└───────────────────────────────────────────────────────────────┘
```

**Why both L1 and L2 in this project** (the recurring checkpoint question):

- NGINX keys on **IP** — it can't authenticate, and it must shed load *before* work
  reaches Python. An anonymous flood dies at the edge.
- DRF keys on **user** — after JWT auth it knows *who*, so limits can be semantic
  (5 login attempts/min vs 120 reads/min). One user behind a shared NAT (office,
  CGNAT) would be unfairly punished by per-IP alone.
- Neither substitutes for the other: per-IP can't express "strict for logins";
  per-user can't stop unauthenticated floods.

---

## 6. Choosing — a decision table

| Situation | Algorithm | Where |
|-----------|-----------|-------|
| Stop unauthenticated floods | leaky bucket (NGINX `limit_req` + `burst`) | edge |
| Login brute-force protection | fixed/sliding counter, strict, **per-user + per-IP both** | app |
| API quota with allowed bursts | token bucket / GCRA | app or gateway |
| Protect a rate-fragile dependency | leaky bucket, sized to the dependency | service client |
| Global distributed fairness | sliding-window counter in Redis | shared |
| Redis down mid-attack | fail-open + alert (abuse) / fail-closed (billing) | policy |

---

## 7. Hands-on exercises (Phase 11)

1. **See the boundary burst:** set a fixed window (5/10s) and a script that sends 5 at
   t=9s and 5 at t=11s — all 10 pass. Reimplement as sliding counter; ~5–6 pass.
   *Lesson: the boundary problem is real.*
2. **Token vs leaky:** configure NGINX `limit_req` (leaky) with `burst=5 nodelay`, then
   a token bucket in front of the same endpoint. Plot accepted-request timestamps —
   leaky smooths, token passes bursts. *Lesson: the two shapes.*
3. **The race:** stand up two processes incrementing a Redis counter with the naive
   GET-then-INCR; watch the limit get exceeded under `ab`/`wrk`. Fix with a Lua
   script; watch it hold. *Lesson: why distributed limiting needs atomicity.*
4. **Fail-open drill:** kill Redis while the app rate-limits against it; confirm your
   chosen policy (and that you *chose* one). *Lesson: the limiter is a dependency.*
5. **Retry storm:** client that ignores `Retry-After` vs one that honors it with
   jitter, against a 429ing endpoint. Watch load graphs. *Lesson: headers are load-
   shaping contracts.*

---

## 8. Interview angles

- **"Design rate limiting for 10M users."** → key choice, algorithm (sliding counter/
  GCRA), shared store + sharding by key hash, local pre-filter to cut Redis load,
  fail-open policy, per-endpoint limits. Mention the retry-storm/herd problem unprompted.
- **"Token bucket vs leaky bucket?"** → burst absorption vs smoothing; "when may I
  send" vs "when do I forward."
- **"Fixed window's flaw?"** → 2× boundary burst; sliding counter as the cheap fix.
- **"Where do you rate limit?"** → layered: edge for survival, app for semantics —
  and the reasons each layer's *key* differs.
- **"Your limiter is a single point of failure — thoughts?"** → fail-open vs
  fail-closed by job (abuse vs billing), local fallback, and the honest answer that
  this is a real trade-off.

---

## 9. Decisions to record in `design.md`

- The layer diagram for this project: NGINX per-IP limits (values) + DRF per-user
  throttles (values, per endpoint class).
- The algorithm at each layer and why.
- Whether any dependency gets its own client-side limiter.
- Fail-open vs fail-closed policy (if/when a shared limiter exists).
- Header set you return on 429 (`Retry-After` + which RateLimit headers).
