# 05 — Service mesh (Envoy sidecar): a load balancer *inside* the pod

## What it is, precisely

A service mesh puts an L7 proxy *next to each pod* (the sidecar pattern). Inter-pod traffic does not go pod-to-pod directly; it goes *through* the proxy. The proxy is where the mesh does its work:

- **Routing**: version-aware (route 80% to v1, 20% to v2), header-based.
- **mTLS**: every hop is mutually-TLS. The mesh terminates and re-encrypts.
- **Resilience**: retries, timeouts, circuit breaking, bulkheads — *per-hop*, not just at the edge.
- **Observability**: the sidecar emits *its own* metrics (requests, retries, connection errors) with per-(source, destination, method) label sets.

## The topology change

Without the mesh:

```
app A pod ──(direct TCP to)──► app B pod
```

With the mesh:

```
app A pod ──► [Envoy on A] ──(mTLS)──► [Envoy on B] ──► app B pod
```

Two extra hops, two extra places where latency and *errors* can appear. The senior engineer's new question: **is the latency in the app, in the mesh, or in the network?** The mesh's metrics are how you answer it.

## The metrics you will read

Envoy (the Istio/Linkerd data plane) exposes a *huge* metric set. The four that matter for this project:

| Metric | Meaning | What a bad value looks like |
|---|---|---|
| `envoy_cluster_upstream_rq_time` | Per-(source,dest) request time, *as seen by the sidecar*. | Climbs while the *app's* p99 is flat → the mesh is the bottleneck (TLS, buffer, connection reuse). |
| `envoy_cluster_upstream_cx_reuse` | Connection-reuse rate to the upstream cluster. | Low = every request opens a new connection. That is *pool* behaviour one layer down; see `database-latency/02`. |
| `envoy_cluster_upstream_rq_retry` | Retries the mesh issued (per the retry policy). | Rising retries = the upstream is flaking; the p99 is *masked* (the retry hides the first failure). |
| `envoy_cluster_upstream_cx_connect_fail` | Connection-establishment failures to the upstream. | Non-zero = the upstream pod is unreachable (network, not app). |

The **retry** metric is the insidious one. A mesh retry policy of "retry on 5xx, 2 times" means a *transient* DB failure is *hidden*: the first attempt 5xxes, the retry 200s, the client sees 200. The app's p99 is fine, *but* the mesh's `rq_retry` is climbing. The system is on the edge of a cliff, and the *request* percentiles do not show it. **Watch the retry count, not just the p99.**

## mTLS and the extra latency

Every hop is now mTLS. The *handshake* is one-time per connection; the *per-request* cost is the TLS overhead (a few microseconds, negligible). The *real* cost is **connection churn**: if the mesh's upstream connection pool is small, requests *queue for a connection* (the `cx_reuse` going low is the tell). That queue is a *mesh-level* pool, a second pool in the stack, on top of the app's DB pool.

Two pools. Two `L_max` knobs. Little's law now has *two* `L_max / W` terms in series. See `capacity/01`.

## The mesh is also a *third* load balancer

The base stack has two LBs: L4 (MetalLB) and L7 (NGINX). The mesh adds a *third*: per-pod, *intra-service*. The routing is now three-deep:

```
L4 (VIP, by IP) → L7 (NGINX, by path) → L7-mesh (Envoy, by header/version)
```

Each layer can *independently* be saturated. A mesh-worker saturation (the sidecar's own CPU) looks like "the app is slow" but is *not* the app. The diagnostic: `envoy_cluster_upstream_rq_time` is high *while* the app's own handler time is low. The gap is the sidecar.

## When a mesh is *wrong*

- **Small service, few pods.** The sidecar's memory (100s of MB per pod) and the extra hop are not worth it. NGINX + kube-proxy is enough.
- **Latency is the SLO, and the mesh adds a hop.** Every extra hop is a *place the p99 can go up*. If your SLO is tight, the mesh's per-hop overhead is a *budget item*, not a free lunch.
- **You do not read the mesh metrics.** A mesh you do not observe is a *hidden* load balancer. The whole point of the mesh is its metrics. Without the dashboards, it is just overhead.

The senior-engineer question: **can I name the panel that would tell me the mesh is the bottleneck?** If yes, the mesh is observability. If no, it is a liability.

## The lab

`load-balancing/labs/mesh-masking.md` — raise the retry policy, make the upstream *flaky*, and watch the p99 stay flat while `rq_retry` climbs. The masked failure is the lesson.
