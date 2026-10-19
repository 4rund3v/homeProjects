# Lab: the cache's two latency shapes, and the stampede

## Prereqs

- The extended stack: app + Redis + Postgres.
- The app uses a cache-aside pattern for `/api/products`: check Redis, miss → Postgres → populate Redis.
- `redis_exporter` running; hit/miss counters visible.

## Step 1 — the two shapes, side by side

Generate a *mix* of requests: 90% for a *hot* key (cached), 10% for *cold* keys (not cached).

Read:
- `redis_keyspace_hits`, `redis_keyspace_misses`. Hit ratio ~0.90.
- App p95 — mostly the *hot* shape. Should be low (~2 ms).
- App p99 — the *cold* shape dominates the tail. Should be ~the DB query time.

The p95 and p99 are *very different numbers*, for a *good* reason: the p95 is in the fast mode, the p99 is in the slow mode. This is a *bimodal* latency distribution, and it is *healthy*. Do not "fix" it by making the p95 match the p99 — that would mean *nothing* is cached.

## Step 2 — drive the hit ratio down

Expire the hot key (or restart Redis, or fill `maxmemory` to evict it). Now the hit ratio drops.

Read:
- Hit ratio — falls from 0.90 to, say, 0.40.
- App p95 — *steps up*. It was 2 ms; now it is closer to the DB query time, because *most* requests are now the slow shape.
- DB pool `pool_in_use` — *rises*. The DB is absorbing the load the cache was.
- DB `mean_exec_time` — *flat* (the DB work is the same). The *count* of DB queries rose, not the per-query cost.

**The step, not the slope.** When the hit ratio drops, the app p95 *steps* (not gradually climbs) to the DB latency. That step is the cache's signature. A *gradual* climb would be a *DB* problem. A *step* is a *cache* problem.

## Step 3 — kill Redis

```
kubectl -n shop delete pod redis-xxxx
```

Watch:
- `redis_keyspace_hits` — flatlines (no cache).
- App p95 — *steps up to the DB query time*. Every request is now the miss shape.
- DB `pool_in_use` — *pins at the pool max*. The DB is taking 100% of the load.
- App p99 — *climbs a cliff*. The pool is saturated; the queue is the story.

**The cache outage is a DB incident.** The Redis panel shows "cache is down," but the *damage* is on the DB pool panel. The senior engineer's reflex: Redis errors → look at the *DB pool*, not just the cache. The cache is the *trigger*; the DB is the *victim*.

## Step 4 — the stampede

Bring Redis back up *empty* (a fresh start, all keys gone). Now drive load. The *first* request for each key misses and queries the DB; without single-flight, the *other* concurrent requests for the *same* key *also* miss and *also* query the DB.

Read:
- `redis_keyspace_misses` — *spikes* (not a steady level).
- DB `pool_in_use` — *spikes in step with the miss spike*, then recovers as the key is populated.
- The miss *spike* and the pool *pin* are *simultaneous*. That simultaneous spike is the stampede.

The fix: **single-flight** (only the first request queries; the others await its result) or a *per-key lock* during populate. The signal you would alert on: `rate(redis_keyspace_misses[1m])` *spiking* *and* `pool_in_use` pinning *at the same time*.

## Restore

Restart Redis with the pre-evicted dataset. Hit ratio returns to 0.90. App p95 steps *back down*. The DB pool un-pins.

## Follow-up questions

- The app p95 is 2 ms at a 0.90 hit ratio. The DB query is 40 ms. What is the *exact* app p95 you would expect if the hit ratio were 0.0? (The miss shape: ~40 ms + the Redis miss RTT. The p95 ≈ 40 ms.)
- If you raised `maxmemory` and the eviction stopped, what *two* things would change? (Hit ratio stays high *longer* — the cache holds more keys. The *stampede* on a key expiry is *rarer*, because keys are evicted less often. The *DB load* drops, because more requests are hits.)
- The hit ratio is high, but the app p99 is *still* high. What is the explanation? (The hit *range* has its own tail: a *large* cached value that takes time to serialize and send. The hit ratio is about *whether* the cache is used, not *how long* the hit takes. A big value is a *slow hit*.)
