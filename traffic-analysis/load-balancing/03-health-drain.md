# 03 — Health checks and connection drain

## The two health checks, in one diagram

```
                    L4 (MetalLB VIP)
                          |
                          |  TCP connect check, ~10-30s
                          v
                   [kube-proxy DNAT]
                          |
                          |  iptables/IPVS refresh, ~30s
                          v
                   [pod IP:port]  <---- L7 (NGINX) HTTP /healthz, ~5s
                          |
                          v
                   [app returns 200]
```

Two independent signals:

- **L4 TCP check**: "can I open a socket to this IP:port?"
- **L7 HTTP check**: "does this pod answer `GET /healthz` with 200?"

They disagree in two common cases:

| L4 | L7 | Meaning |
|---|---|---|
| up | up | all good |
| up | down | app broken, TCP alive. Rolling update mid-way, or app OOM but container not killed yet. |
| down | up | node problem, pod still thinks it is fine. Rare. |
| down | down | pod is gone. Expected. |

## The 10-second window

This is the lab in `project/labs/break-the-system.md` (break 1). You kill a pod. The L4 layer does not notice for 10–30 s. The L7 layer notices in 5 s. During the gap:

- L4 keeps sending to the dead pod's IP.
- Those connections time out (the kernel drops them).
- The L7 layer, *if it is in the path*, would have stopped sending new requests. But the L4 path is *in front of* the L7 layer — the client's TCP connection lands on the dead pod's IP before NGINX ever sees it.

So the L4 layer is the *first* layer to see a dead pod, and it is the *slowest* to notice. That is the structural problem.

## Connection drain, precisely

A pod deletion is not atomic. The sequence:

1. `kubectl delete pod shop-api-xxxx`
2. The pod gets `terminationGracePeriodSeconds` (default 30 s) to drain.
3. During the drain, the pod's endpoints are removed from the `Service`'s `endpoints` object.
4. `kube-proxy` updates iptables/IPVS (~30 s).
5. NGINX updates its upstream list (~5 s, on `endpoints` watch).
6. The pod's container gets `SIGTERM`.
7. The pod exits.

Step 5 (NGINX) is the *L7 drain* — NGINX stops sending new requests to the draining pod. Step 4 (kube-proxy) is the *L4 drain*. Steps 3–4 are the slow one. The pod still exists in `endpoints` until kube-proxy refreshes, and NGINX still sees it until its own watch fires.

The `preStop` hook is the only way to *control* the order. A typical one:

```yaml
lifecycle:
  preStop:
    exec:
      command: ["sh", "-c", "sleep 5"]
```

The 5 s is the "wait for the LB to forget me" delay. Too short and the LB keeps sending; too long and the pod takes longer to drain.

## What to observe

- `kubectl -n shop get endpoints shop-api` during a delete. Watch the `endpoints` shrink.
- `nginx_ingress_controller_upstream_check_fails` — NGINX's L7 health check failures.
- `kube_pod_status_ready` — the k8s view of pod readiness.

The lab in `load-balancing/labs/kill-a-pod.md` measures all three.
