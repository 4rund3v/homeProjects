# Lab: baseline observation

The first lab is the one you must complete before touching any topic doc. It gives you a reference line against which every later "break the system" lab is measured.

## Prereqs

- Everything in `02-deploy.md` running.
- `k6` on the host (or `ab`).
- Grafana admin login working.
- One terminal that stays on `kubectl logs -f -n shop deploy/shop-api`.

## Steps

1. **Idle.** No load. Watch Grafana for 2 minutes. Record:
   - `kube_pod_container_resource_usage:sum:rate5m` for `shop-api` — idle CPU.
   - `rate(http_request_duration_seconds_count[5m])` — idle RPS (should be ~0).
   - `pg_stat_activity_numbackends` — idle connection count.
   - `nginx_ingress_controller_connections_active` — idle connections.

2. **Low load.** `k6` at 5 VU for 60s. Record the same 4 metrics. Compute:
   - p50 from `histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint))`.
   - p95 and p99 same shape.
   - Note: at 5 VU, p50 ≈ p95 ≈ p99. All should be under 50 ms.

3. **Medium load.** 50 VU for 60s. Same queries. Note:
   - p95 starts to separate from p50. By how much?
   - `pg_stat_statements` mean_exec_time — is it moving?
   - `node_disk_read_time_seconds_total` — is the PVC showing I/O?

4. **High load.** 200 VU for 60s. Same queries. Note:
   - p99 now dominates the story.
   - Are `http_request_duration_seconds_count` rate and `nginx_ingress_controller_request_duration_seconds_count` rate the same? (They should be, if you are the only client.)
   - Any `5xx`? Any timeouts?

5. **Stop.** Wait for load to drain. Watch each metric return to its idle line. Time it.

## Output

A single page with the 4 metrics, at the 4 load points. Each line:

```
idle / 5 VU / 50 VU / 200 VU:
  RPS app           0     5      50       200
  RPS nginx         0     5      50       200
  p50               8ms   9ms    14ms     61ms
  p95               8ms   10ms   22ms     210ms
  p99               9ms   11ms   40ms     890ms
  pg mean_exec_time 4ms   4ms    6ms      32ms
  pg backends       2     3      8        25
```

Numbers will differ — the point is the shape. p50 flat then p95 then p99 peeling off, in that order, is the expected signature.

## Follow-up questions (answer before moving on)

- At 200 VU, is the p99 explosion driven by CPU, by DB, by network? Which one, and how did you tell?
- If a customer reported "it's slow" at 200 VU, which single panel would you screenshot to explain?
- If you doubled to 400 VU, what would you *predict* p99 does, and why?
