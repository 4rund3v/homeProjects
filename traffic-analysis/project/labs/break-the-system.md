# Lab: break the system, one way at a time

Run each break, read the metrics, and answer the question at the bottom. Restore the system between breaks.

## Break 1: kill one app pod

```
kubectl -n shop delete pod shop-api-xxxx
```

Watch for 60s:
- `nginx_ingress_controller_request_duration_seconds_bucket` — should be flat (L7 health check kicks in within ~10s).
- `kube_pod_info{pod="shop-api-xxxx"}` — pod gone.
- The remaining pod's `rate(http_request_duration_seconds_count[1m])` — should double.
- `MetalLB` VIP — does it keep sending to the dead pod's IP? (L4 has no app awareness — yes, until kube-proxy updates iptables.)

**Question:** what was the p99 during the 10-second window where the dead pod still accepted connections? That is the L4/L7 difference, measured.

## Break 2: fill the DB pool

Edit the app to hold connections (or set `poolMaxConns: 4` on the app and hold 4 open in a tight loop). Re-load at 200 VU.

Watch:
- `pg_stat_activity_numbackends` — pinned at 4.
- `pg_stat_statements` for the two queries — mean_exec_time spikes.
- App `http_request_duration_seconds_bucket` — p99 explodes, p50 mostly flat.
- New errors: `SELECT` timeouts in app logs.

**Question:** which metric warned you *first*? Pool saturation is a leading indicator, not a lagging one.

## Break 3: slow the PVC

Simulate slow disk:

```
kubectl -n shop exec -it postgres-0 -- iostat -x 5
```

Now pause the pod or write a big file on the PVC:

```
kubectl -n shop exec -it postgres-0 -- dd if=/dev/zero of=/pgdata/bigfile bs=1M count=2048
```

Watch:
- `node_disk_io_time_seconds_total` on the host.
- `pg_stat_statements` for `VACUUM`-like queries and checkpoints.
- App p99 — the PVC slowness leaks up the stack.

**Question:** one line in `pg_stat_statements` should be spiking. Which one, and why?

## Break 4: release a bad image tag

Push `shop-api:v0.1.1` with an intentional bug (e.g., sleeps 2s on `/api/orders`). Deploy with `:latest` in the image field, then force an image pull by restarting pods.

Watch:
- `http_request_duration_seconds_bucket{endpoint="/api/orders"}` — p50 jumps 2s.
- `http_request_duration_seconds_bucket{endpoint="/api/products"}` — flat. That is the fingerprint of a per-endpoint regression.
- The L4 LB has no idea. L7 also has no idea (request still returns 200 in ~2s).
- `pg_stat_statements` flat.

**Question:** what is the only metric that would have caught this? `http_request_duration_seconds` on the specific endpoint. Why is that the lesson for release pipelines?

## Break 5: scrape interval blind spot

Restart Prometheus with `--scrape-interval=60s`. Generate a 10-second p99 spike (kill one pod again).

Watch:
- `histogram_quantile(0.99, ...)` — the spike does not show. 60s granularity swallows 10s events.
- `histogram_quantile(0.50, ...)` — barely moves.

**Question:** why does "we have Prometheus, we see everything" fail? The answer is in `observability/02-cardinality` and `capacity/01-littles-law`.

## Restore between breaks

```
kubectl -n shop rollout status deploy/shop-api
kubectl -n shop delete pvc --all   # only if PVC is broken
helm -n observability restart prometheus
```

After restore, run the baseline lab's 4-point table again. The lines should return to their idle shape.
