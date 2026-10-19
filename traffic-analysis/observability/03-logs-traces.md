# 03 — Logs, traces, and when each one is the right tool

## The three questions, restated

| Question | Tool |
|---|---|
| How many? How fast? How many errors? | **Metric** |
| Which specific one? What did it log? | **Log** |
| What path did it take through the system? | **Trace** |

The mistake is using the *wrong one* for the question. Grep-ing logs for "how many requests failed" is slow and wrong. Using a metric to find "which request failed" is impossible (metrics are aggregates).

## Logs in this project

The app and NGINX both log to stdout. `kubectl -n shop logs deploy/shop-api` is the reader. A real enterprise service ships stdout to a log store (Loki, CloudWatch, S3) and queries it there.

The one rule for logs: **every line must carry a correlation ID** (a request ID, a trace ID, a user ID). Without it, you cannot join a log line to a metric panel or a trace. The reference app in `project/examples/` should print a `req_id` per request; that is the join key.

## Traces: the shape

A trace is a tree of spans. One span per "unit of work" — a request to the app is one span; the DB query inside it is a child span; the TLS handshake is another.

```
[request: /api/orders]  450 ms
  ├─ [ingress: TLS + proxy]  3 ms
  ├─ [app: handler]  420 ms
  │    ├─ [db: SELECT]  380 ms   <-- the slow part
  │    └─ [app: serialize]  30 ms
  └─ [ingress: log write]  2 ms
```

The trace shows *where* in the 450 ms the time went. The metric (p95 = 450 ms) shows *how much*. The log shows *what the request was*. All three are needed to answer "why is p95 450 ms."

## Adding traces to this project (stretch)

The reference app does not export traces. To add them:

- A trace exporter (Jaeger, Tempo, or the cloud's).
- The app wraps each handler in a span; the DB driver wraps each query in a child span.
- A `trace_id` propagates from the ingress (an `X-Trace-Id` header) to the app to the DB.

The dashboard panel is not a trace panel. It is a *link*: "p95 is 450 ms → click to see the trace of the request that set the p95." The metric is the *trigger*; the trace is the *detail*.

## The mistake you will make, and the fix

A service has p95 = 2 s. The engineer opens the *log* of a slow request and sees "SELECT took 1.8 s." Conclusion: "the query is slow." Fix: add an index.

The correct next step is the *trace*: the 1.8 s is not the query. It is the *wait for a DB connection* (1.5 s) + the query (0.3 s). The trace shows the two spans; the log does not. The fix is the *pool*, not the index. See `database-latency/02`.

## The lab

`observability/labs/logs-traces.md` — open a slow request's trace and its log side by side, and name the two different answers each one gives.
