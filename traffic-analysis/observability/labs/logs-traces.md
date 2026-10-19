# Lab: logs vs traces, two answers to one question

## Prereqs

- The reference app running, with a `req_id` per request in the logs (patch the reference app if it does not have one).
- A trace exporter (Jaeger or Tempo) is a *stretch* for this project. Without it, this lab degrades to "logs only," which is the point — you will see what you *cannot* answer with logs alone.

## Step 1 — pick a slow request

Under 200 VU, the app p99 is high. Find a request in the log that took > 1 s:

```
kubectl -n shop logs deploy/shop-api | awk '{ if ($3 > 1.0) print }'
# or, if the app logs JSON:
kubectl -n shop logs deploy/shop-api | jq -c 'select(.duration_ms > 1000)'
```

Pick one. Record its `req_id`.

## Step 2 — the log's answer

Grep the log for that `req_id`. You get every log line the app wrote for that request:

```
req_id=abc123 GET /api/orders
req_id=abc123 db: SELECT ... in 320ms
req_id=abc123 db: SELECT ... in 28ms
req_id=abc123 handler done in 410ms
req_id=abc123 response 200 in 415ms
```

The log says: *the request took 415 ms, and the DB calls total 348 ms.* The log does *not* say: *where the other 67 ms went, and whether the request was waiting for a pool connection.*

## Step 3 — the trace's answer (if you added traces)

Open the trace for `req_id=abc123`. You see the span tree:

```
[request] 415 ms
  ├─ [db conn acquire]  120 ms   <-- the pool wait
  ├─ [db: SELECT]         320 ms
  └─ [db: SELECT]           28 ms
```

The trace says: *120 ms was waiting for a pool connection, 348 ms was actual query time, and the two overlap partially.* The log did not have that span.

## Step 4 — without the trace

If you did *not* add a trace exporter, the answer to "where did the 67 ms go" is: *you do not know, from the log.* The log tells you the total and the DB-call totals. The gap is the *queue* (pool wait), and the log does not record queue time.

That is the lesson. The log is the *which request*. The trace is the *what path*. Without the trace, the gap is invisible.

## Question

You have a p99 of 2 s. The log says "DB call took 1.8 s." You add an index, re-deploy, and the p99 is *still* 2 s. Why? (The log's "1.8 s DB call" included the *pool-wait* time, not just the query. The index made the query faster, but the pool was still saturated. The trace would have shown the two spans separately.)
