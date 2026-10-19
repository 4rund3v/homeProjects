# 02 — Deploy order, and what to verify after each step

Deploy in this order. Each step ends with a verify command. If a verify step fails, do not move on — the next step builds on a broken previous step and you cannot tell which one broke.

## 0. Prereqs on the host

```
kubectl cluster-info                # cluster reachable
helm version                        # helm v3
docker version                      # or podman, for building the app
kind get kubeconfig                # or k3s, depending on your cluster
```

## 1. Local registry (artifact repo)

Deploy `registry:2` as a Deployment with a `Service` of type `NodePort`. One PVC if you want images to survive.

```
kubectl -n artifacts get pods
kubectl -n artifacts get svc registry
```

Get the NodePort IP: `kubectl get nodes -o wide`, then `curl -v http://<node-ip>:<nodeport>/v2/`. Should return 200 or 401 — both prove the registry is up.

Push a test image:

```
docker tag hello-world local:<nodeport>/hello-world
docker push local:<nodeport>/hello-world
```

If `docker push` fails on TLS, configure `insecure-registries` in daemon.json for that NodePort. This is a classic production incident in itself — a registry that moved to HTTPS and half the nodes still trust the old.

## 2. MetalLB (L4)

Helm install metallb into `metallb` ns. One `IPPool` CR with a CIDR the cloud/host can actually route (for kind: a host IP, or `192.168.x.0/24` if you control the LAN). One `L4LoadBalancerPolicy` if you want `externalTrafficPolicy: Local`.

```
kubectl -n metallb get pods
kubectl get ipaddresspool
```

Verify: create a test Service of type `LoadBalancer` in any ns; within ~30s it should get a `.status.loadBalancer.ingress[0].ip`. If it stays `<pending>`, MetalLB's `BGP`/`Layer2` peer is not talking to your switch.

## 3. NGINX Ingress (L7)

Helm install `ingress-nginx` chart into `ingress-nginx` ns. One `Service` of type `LoadBalancer` (MetalLB will fill in the VIP). Annotations on the Service for prometheus:

```
prometheus.io/scrape: "true"
prometheus.io/port: "10254"
```

```
kubectl -n ingress-nginx get pods
kubectl -n ingress-nginx get svc ingress-nginx-controller
```

Verify: `kubectl -n ingress-nginx get svc` shows the VIP. `curl -v http://<vip>/` should return 404 (no ingress yet) — that proves the L7 path is alive and you are talking to nginx, not to the cluster.

## 4. Postgres + PVC + app

Helm install `bitnami/postgresql` into `shop` ns. Enable `pg_stat_statements`:

```
primary.existingExtensions: "pg_stat_statements"
```

Deploy the Go app (`examples/app/main.go` is a 100-line reference). It reads `DATABASE_URL` from a secret, serves `/api/products` and `/api/orders`.

Push the image to the local registry:

```
docker build -t local:<nodeport>/shop-api:v0.1.0 ./examples/app
docker push local:<nodeport>/shop-api:v0.1.0
```

Deploy with the tag pinned:

```
image: local:<nodeport>/shop-api:v0.1.0    # pinned, never :latest
```

## 5. Observability

Helm install `prometheus-community/prometheus` into `observability` ns. Scrape interval: start at 15s, not 30s — one of the labs in this repo is "how does scrape interval affect your p99."

Install `node-exporter` daemonset and `postgres-exporter` in `shop` ns (it needs the same credentials as the app).

Install Grafana with an admin password. Import the dashboards in `project/examples/` — one per topic.

## 6. End-to-end verify

Generate load from the host:

```
k6 run -vusages examples/load-test/k6-ramp.js
# or
ab -n 1000 -c 20 http://<vip>/api/products
```

Now:

```
kubectl top pods -n shop
kubectl -n shop logs deploy/shop-api | tail
```

Open Grafana. Every panel in `project/examples/dashboards/main.json` should be moving. If a panel is empty, the corresponding scrape target is failing — check `Prometheus / Targets` and the pod's own `:9113/metrics` (postgres-exporter) or `:10254` (nginx).

## What to read before you move to topic docs

Before you start `latency-percentiles/`, sit in Grafana for 15 minutes and, for each panel, answer out loud:

- What promql is this panel running?
- What is the unit?
- What does a "bad" value look like?
- If this panel spiked, which *other* panels would I also check?

If you cannot answer for a panel, it is not yet a panel you understand. That is fine — that is the reason for the topic docs that follow.
