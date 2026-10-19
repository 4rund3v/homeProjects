# Lab: kill a pod, measure the L4/L7 gap

## Prereqs

- App + NGINX + MetalLB up, 50 VU steady load running.
- Two terminal windows: one on `kubectl -n shop get pods -w`, one on `kubectl -n shop get endpoints shop-api -w`.

## Step 1 — steady state

Record for 60 s:
- `nginx_ingress_controller_request_duration_seconds_bucket` p95.
- `http_request_duration_seconds_bucket` p95.
- `sum by (pod) (rate(http_request_duration_seconds_count[1m]))` — RPS per pod. Should be even.

## Step 2 — kill a pod

```
kubectl -n shop delete pod $(kubectl -n shop get pod -l app=shop-api -o jsonpath='{.items[0].metadata.name}')
```

Start a stopwatch. For the next 60 s, every 10 s, record:
- `sum by (pod) (rate(http_request_duration_seconds_count[1m]))` — how many pods still serving.
- `nginx_ingress_controller_upstream_response_time` (if available) — L7 upstream time.
- Any `502` / `504` in `nginx_ingress_controller_status_code`.
- The new pod's readiness (`kube_pod_status_ready{pod=~"shop-api-.*"}`).

## Step 3 — answer the questions

1. **How long did the L4 layer keep sending to the dead pod's IP?** Read the endpoints shrink time. `kubectl -n shop get endpoints shop-api -w` should show the dead endpoint disappear in ~10–30 s. That is the L4 gap.

2. **How long did the L7 layer take to stop sending?** NGINX's `upstream_check_fails` should spike. Read the timestamp.

3. **Which layer's p99 hurt more?** The L4 path (client → VIP → dead pod IP) times out. The L7 path (client → VIP → NGINX → live pods) is fine. The delta is the L4/L7 gap, in ms.

4. **When did the new pod start taking traffic?** `kube_pod_status_ready` goes true, then NGINX's upstream list updates, then RPS on the new pod appears. The sum of those three is the "recovery time." A senior engineer budgets for it.

## Restore

```
kubectl -n shop rollout status deploy/shop-api
```

Wait until all pods `Ready` and `sum by (pod) (...)` is even again.
