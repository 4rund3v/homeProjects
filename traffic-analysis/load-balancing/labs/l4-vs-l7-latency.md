# Lab: L7 vs L4 latency, measured

## Prereqs

- App + NGINX + MetalLB up.
- 50 VU steady load.
- `kubectl exec` into the NGINX pod to read its CSV log (see `project/examples/helm-values.yaml` for the `enable-csv-log-format` annotation).

## Step 1 — the L7 view

```
kubectl -n ingress-nginx exec -it ingress-nginx-controller-xxxx -- \
  tail -1000 /var/log/nginx/shop-access.log | head -20
```

Each CSV line has: `request_time`, `upstream_response_time`, `upstream_connect_time`.

- `request_time` = total time the client saw (includes TLS, proxy, upstream, log write).
- `upstream_response_time` = time the app took to answer (includes DB).
- `upstream_connect_time` = time to open a TCP connection to the app pod.

The delta `request_time - upstream_response_time` is *NGINX's own overhead*. Under 50 VU it should be < 5 ms. Under 200 VU it grows.

## Step 2 — the L4 view

The L4 VIP does not log per-request. You measure it by *timing the client side*:

```
# 100 requests, record each duration
for i in $(seq 1 100); do
  curl -o /dev/null -s -w "%{time_total}\n" http://<vip>/api/products
done | sort -n | awk '{a[NR]=$1} END {printf "p50=%.3f p95=%.3f p99=%.3f\n", a[int(NR*0.5)], a[int(NR*0.95)], a[int(NR*0.99)]}'
```

This is the *end-to-end* latency the client sees: client → L4 VIP → node → kube-proxy → pod → NGINX → app → DB → back.

## Step 3 — compare

| Metric | What it includes |
|---|---|
| App `http_request_duration_seconds` p95 | app + DB only |
| NGINX `request_duration_seconds` p95 | + TLS + proxy + upstream connect |
| Client `curl time_total` p95 | + L4 VIP + node + kube-proxy + network RTT |

Each row adds a layer. The *delta* between rows is the *cost* of that layer. A senior engineer knows each delta:

- App → NGINX delta: TLS + proxy, 1–5 ms.
- NGINX → client delta: L4 path, 2–10 ms.
- Client → server round-trip: 1–50 ms (network distance).

## Question

At 200 VU, the client p95 is 400 ms. The NGINX p95 is 380 ms. The app p95 is 210 ms. Where is the other 170 ms?

(A: NGINX upstream queue. The L7 layer is saturated, and requests are waiting in NGINX's own queue for a free worker. See `capacity/02`.)
