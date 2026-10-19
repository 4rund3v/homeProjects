# Lab: the mesh masks a flapping upstream

## Prereqs

- The extended stack running (mesh, cache, queue).
- The app's *upstream dependency* (e.g. app B, or the cache) that you can make *flaky* on demand.

## The setup

The mesh retry policy is: `retryOn: 5xx,reset`, `numRetries: 2`. The upstream (app B) will be made to 500 on *every third* request (a deliberate flakiness you inject with a test toggle).

## Step 1 — the masked p99

Generate steady load. The upstream 500s on 1/3 of requests, but the mesh *retries* each, so the client sees 200s almost always.

Read:
- App p99 — *flat*. The retries hide the failures.
- `envoy_cluster_upstream_rq_retry` — *climbing* steadily. This is the tell.
- `envoy_cluster_upstream_rq_time` — *higher* than idle, because some requests took two attempts.

**The lesson:** the request p99 says "all good." The mesh retry metric says "the upstream is flapping." One of them is wrong. *Which do you trust?* The retry count. The p99 is *masked*.

## Step 2 — the cliff

Keep the flakiness. Increase the load until the upstream is 500ing on *most* requests, not 1/3. Now the retries *also* 500, and the client starts seeing 5xx.

Read:
- App p99 — *climbs a cliff* (timeouts on the retried requests).
- `envoy_cluster_upstream_rq_time` — the *p99* of it, not the mean. A retry *doubles* the request time (two attempts). The p99 of request time is now ~2× the p99 of the single-attempt time.
- `envoy_cluster_upstream_cx_connect_fail` — if the upstream is *down* (not just flaky), this goes non-zero.

The transition from "masked" to "cliff" is the *capacity limit of the retry policy*: retries are headroom, not a fix. Past the headroom, the failures surface.

## Step 3 — the *real* fix

The fix is *not* "raise the retry count." The fix is the upstream: why is app B 500ing? The mesh metric *pointed* you there. The retry was *masking* the root cause for a while, and the senior engineer's habit is: **a climbing `rq_retry` is an incident, even if the p99 is flat.**

## Restore

Remove the flakiness toggle. `rq_retry` drops to 0. The p99 returns to idle. The *root cause* is fixed, not masked.

## Follow-up questions

- The mesh hides *transient* failures. What does it *amplify*? (A retry storm: N clients × M retries = N×M upstream requests. A flaky upstream + retries = a *load amplifier*, which is how a flaky dependency takes down the caller. This is the `capacity/03` queueing story, one layer up.)
- If the upstream is *rate-limited* (returns 429), and the mesh retries on 429, what happens? (The retries make the rate-limit *worse*. Retrying on 429 is almost always a bug in the retry policy. The senior engineer knows *which* status codes to retry on: 503, reset, connection-error — *not* 4xx.)
