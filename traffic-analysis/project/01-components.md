# 01 — Components, versions, and what each one actually does

## Cluster

- **kind** (or k3s, or a real cloud cluster — kind is fine for learning). Single control plane, 2-3 workers, 4 GiB RAM minimum each.
- `kubectl` and `helm` installed on the host. `kubectl get nodes` should show `Ready`.

## In-cluster

| Workload | Image / chart | Where it lives | Why it exists here |
|---|---|---|---|
| MetalLB | `metallb` chart, `v0.14.x` | `metallb` ns | L4 LB: gives the cluster a public VIP. You will observe TCP-level LB. |
| NGINX Ingress | `ingress-nginx` chart, `v4.x` | `ingress-nginx` ns | L7 LB: HTTP routing, TLS, request-time tracking. Most metrics in this repo come from here. |
| App | your Go service, built locally, pushed to local registry | `shop` ns, Deployment `shop-api`, HPA optional | Source of latency. Two endpoints, one Postgres query each. |
| Postgres | `bitnami/postgresql` chart, `v15`+ | `shop` ns | The slow resource. `pg_stat_statements` extension on. |
| PVC | `standard` storage class, 10 GiB | same as PG | Lets you watch disk I/O and what happens when the PVC is on a slow node. |
| Registry | `registry:2` deployment + Service NodePort | `artifacts` ns | The artifact repo. App image is pushed here, then deployed from here. |
| Prometheus | `prometheus-community/prometheus`, `v248`+ | `observability` ns | Scrapes everything. You will watch what scrape interval does to the p99s. |
| Grafana | `grafana` chart | `observability` ns | Panels. Every topic in this repo will name a panel by name. |
| Alertmanager | same chart | `observability` ns | Wires alerts. You will watch alert flapping. |
| node-exporter | `prometheus-community/prometheus-node-exporter` | daemonset | CPU, memory, disk I/O per node. |
| postgres-exporter | `prometheus-community/postgres-exporter` | `shop` ns | DB-side metrics: connections, replication, cache. |

## Versioning note

Pin versions in the lab. Floating `latest` in the registry is a real incident source — one of the labs in `project/labs/` is "release one bad tag, watch it float across all replicas."

## Namespace layout

```
metallb/          # L4
ingress-nginx/    # L7
shop/             # app + postgres + pvc
artifacts/        # registry
observability/    # prometheus, grafana, alertmanager
```

One rule: every `ServiceMonitor` (or `PodMonitor`) you add must scrape a pod in the same namespace unless you explicitly write a cross-ns selector. The observability topic walks through why this matters.
