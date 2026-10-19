# 00 — The three signals, and when each one is the right tool

Metrics, logs, traces. A senior engineer picks the right one per question, not per tool.

| Question | Tool | Why |
|---|---|---|
| "How many requests in the last 5 m?" | **Metric** | A rate, a number, no need to read lines. |
| "Which requests were slow?" | **Metric** | A histogram quantile, a number. |
| "Which *specific* request was slow, and why?" | **Log** (with a trace ID) | One line, one request, one stack. |
| "What was the *path* of a slow request through the system?" | **Trace** | The span graph. |
| "Did we deploy a bad version at 3am?" | **Metric** + **log** | The metric shows the jump; the log shows the error. |

## The rule you will keep re-learning

**Metrics are for *how much*. Logs are for *which one*. Traces are for *what path*.**

A dashboard full of logs is a waste. A trace system that does not export metrics is a waste. The three are *complementary*, and the senior engineer knows which question each one answers.

## Where in this project

- **Metrics**: Prometheus (the whole observability stack).
- **Logs**: the app and NGINX both log to stdout; `kubectl logs` is the reader. A real enterprise service ships them to Loki or similar.
- **Traces**: the reference app does not export traces. Adding them is a stretch goal; the shape is in `observability/03`.

## The three panels every service must have

1. **RED** on the app (Rate, Errors, Duration) — `01-red-use`.
2. **USE** on the node (Utilization, Saturation, Errors) — `01-red-use`.
3. **The SLO burn-rate panel** — `latency-percentiles/03`.

Everything else is a *detail* panel. The three above are the *triage* panels. If one of them is red, stop and look at it before you look at anything else.
