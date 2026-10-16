# 02 — Kubernetes Core: The Runtime Everything Sits On

**Folder:** `02-kubernetes-core/`
**Milestone:** M2 — Core runtime

---

## Teach first: what Kubernetes actually is

### The one-sentence definition

Kubernetes is a **declarative control loop engine** that drives a set of machines toward a desired state you describe.

Strip away the branding and k8s is: *a database of desired state* (etcd) + *controllers that reconcile reality to match it* + *a scheduler that decides where work runs* + *an API that everything talks to*.

### The reconciliation loop — the single most important idea

Every Kubernetes controller runs the same loop, forever:

```
loop:
    desired  = read_desired_state()   # from the API server
    actual   = observe_reality()      # talk to the world
    if actual != desired:
        act_to_close_the_gap()
    sleep()
```

This is why a Deployment with `replicas: 3`, where you `kubectl delete pod`, heals itself. Nobody "creates a pod." A controller notices 2 pods exist, desired is 3, and creates one. **You never command Kubernetes; you declare, and it reconciles.**

This reframes how you debug: if reality doesn't match your declaration, either (a) your declaration isn't what you think, or (b) a controller can't close the gap (insufficient resources, a bad image, a scheduling constraint).

### The control plane — the brain

| Component | Job |
|---|---|
| **kube-apiserver** | The front door. All reads/writes go through it. Validates, authenticates, authorizes, persists to etcd. |
| **etcd** | The distributed key-value store — the *only* source of truth for cluster state. |
| **kube-scheduler** | Decides which node a pending pod runs on, using resource requests, affinity, taints/tolerations. |
| **kube-controller-manager** | Runs the built-in controllers (Deployment, ReplicaSet, Node, Job, etc.). |
| **cloud-controller-manager** | In cloud, bridges to the provider's load balancers, volumes, etc. Absent in bare-metal homelabs. |

### The worker node — the muscle

| Component | Job |
|---|---|
| **kubelet** | The node agent. Watches for pods assigned to this node, starts their containers, reports status. **The kubelet is the thing that actually runs your containers.** |
| **kube-proxy** | Programs iptables/IPVS rules so Services route to the right pods. |
| **container runtime** | containerd (usually). Actually pulls images and runs containers. |

> **Senior lens** — when a pod is `Pending`, the problem is on the **scheduling** side (no node fits). When it's `CrashLoopBackOff`, scheduling succeeded and the problem is **inside the container**. When it's `ContainerCreating` forever, the problem is usually **volumes or image pulls**. Knowing which of the three buckets you're in cuts debug time drastically. We'll cover this in the *Debugging* section.

---

## The objects you must internalize

### Pod — the unit of execution

A pod is one or more containers sharing a network namespace and, optionally, volumes. Pods are **ephemeral by design**: they are not meant to be moved, only destroyed and recreated. This is why you almost never create bare pods — you create *controllers* that manage pods for you.

### Workload controllers

| Controller | Use for |
|---|---|
| **Deployment** | Stateless apps. Rolling updates, rollbacks, replicas. Outline's API and workers. |
| **StatefulSet** | Stateful apps needing stable identity + stable storage. Postgres, Redis. |
| **DaemonSet** | One pod per node. node-exporter, Promtail, CNI plugins. |
| **Job / CronJob** | Run-to-completion. Migrations, backups, cron tasks. |

> **Tradeoff — Deployment vs. StatefulSet.** A Deployment's pods are interchangeable and get random names (`app-7d9f...`). A StatefulSet's pods get *ordinal, stable* names (`postgres-0`, `postgres-1`) and each gets its *own* PVC that survives rescheduling. You use a StatefulSet when the identity of a pod matters — because data is attached to it, or because peers need to address each other deterministically. Using a Deployment to run a database is a classic beginner mistake: pods swap identities and lose their data. **Postgres ⇒ StatefulSet, always.**

### Service — stable networking over ephemeral pods

Pods come and go with new IPs. A **Service** gives a stable virtual IP (ClusterIP) and DNS name that load-balances across the pods matching its selector. Types:

- **ClusterIP** (default) — internal only.
- **NodePort** — exposes on every node's IP:port. Rarely the right answer.
- **LoadBalancer** — asks the infra for an external LB. In bare metal, needs something like MetalLB to fulfill.
- **ExternalName** — a CNAME alias.

### Ingress — HTTP routing into the cluster

A Service with type LoadBalancer gives you one IP per service. **Ingress** gives you *one entry point* routing by hostname/path to many services. It requires an **ingress controller** (we install ingress-nginx in doc 01).

```
outline.lab.example    → outline-service:3000
harbor.lab.example     → harbor-service:80
grafana.lab.example    → grafana-service:80
```

### ConfigMap and Secret

- **ConfigMap** — non-sensitive config, injected as env vars or mounted files.
- **Secret** — sensitive data, base64-encoded (NOT encrypted by default!). Storing a Secret in etcd is *not* security — etcd needs encryption-at-rest configured, and RBAC must restrict who can read Secrets.

> **Failure mode / common misconception** — `kubectl get secret -o yaml` shows base64, which many people think is "encryption." It's encoding. Anyone with read access to the namespace can decode it instantly. Real secret security needs (a) etcd encryption at rest, (b) tight RBAC, (c) ideally an external secret manager (Sealed Secrets, External Secrets Operator, Vault). Doc 14 covers this.

### PersistentVolume (PV) and PersistentVolumeClaim (PVC)

This is the distinction that trips everyone up:

- **PV** — the actual storage resource (an NFS share, a local disk, a cloud volume). Cluster-scoped.
- **PVC** — a *request* for storage by a workload ("I need 20Gi, ReadWriteOnce"). Namespace-scoped.
- **StorageClass** — a template that tells the cluster how to *dynamically provision* a PV when a PVC is created. This is what makes PVCs self-service.

```
Pod  →  PVC (request)  →  StorageClass (provisioner)  →  PV (actual storage)
```

> **Tradeoff — access modes.** `ReadWriteOnce` (RWO) means a volume mounts on one node at a time. `ReadWriteMany` (RWX) allows many nodes but requires a filesystem that supports it (NFS, CephFS) — plain block storage can't do it. For Postgres you want RWO (one writer). For MinIO you might want RWX depending on setup. Choosing wrong here causes pods to get stuck in `ContainerCreating` with a "volume is already attached to another node" error.

> **Threshold — reclaim policy.** `Delete` (default for dynamic PVs) destroys the underlying storage when the PVC is deleted. `Retain` keeps it. For databases, the difference is "I deleted a PVC and lost the data" vs. "I deleted a PVC and can re-attach the data." **For anything you care about, use `Retain` + a backup.**

---

## Scheduling: how the scheduler thinks

The scheduler places a pod by filtering and scoring nodes:

1. **Filter** — which nodes *can* run this pod? (enough CPU/mem, matching nodeSelector/affinity, tolerating taints)
2. **Score** — among those, which is *best*? (spread, resource balance, affinity preferences)

Knobs you'll use:

- **resources.requests / limits** — requests are what the scheduler reserves; limits are the hard cap.
- **nodeSelector / nodeAffinity** — pin pods to nodes (e.g. Postgres to the node with the SSD).
- **taints / tolerations** — the inverse: nodes repel pods unless the pod tolerates the taint. Used for dedicated nodes.
- **PodDisruptionBudget (PDB)** — guarantees a minimum number of pods stay up during voluntary disruptions (node drains, upgrades).

> **Threshold — requests matter more than limits for scheduling.** The scheduler ignores limits when deciding placement; it uses requests. If you set requests too low, the node gets oversubscribed and pods get OOM-killed or evicted under pressure. If you set them too high, pods sit `Pending` forever because no node "fits." **Setting requests right is the single most impactful thing you can do for cluster stability.**

> **Senior lens — always set a PDB for anything with >1 replica.** Without a PDB, a node drain can evict all your Postgres replicas or all your Outline API pods simultaneously. The PDB is what turns "the whole service went down during maintenance" into "we kept quorum."

---

## Quality of Service (QoS) classes

The kubelet uses requests/limits to assign a QoS class, which decides **eviction order** under node pressure:

| Class | Condition | Evicted |
|---|---|---|
| **Guaranteed** | requests == limits for all containers | Last |
| **Burstable** | requests < limits somewhere | Middle |
| **BestEffort** | no requests/limits at all | First |

> **Tradeoff** — Guaranteed protects a pod but wastes capacity (you reserve the max). BestEffort packs tightly but gets evicted first. For databases, lean **Guaranteed** (predictable). For bursty web APIs, **Burstable** is the sweet spot.

---

## Namespaces and multi-tenancy

Namespaces are logical partitions for names, RBAC, and resource quotas. Plan yours now:

```
kube-system        # cluster internals
ingress-nginx      # ingress controller
cert-manager       # TLS
monitoring         # prometheus, grafana, loki
database           # cloudnative-pg + postgres clusters
cache              # redis
storage            # minio
identity           # keycloak
cicd               # jenkins
registry           # harbor
outline            # the app
```

> **Senior lens** — namespaces are the unit of **blast radius**. A runaway pod in `outline` should not be able to consume all cluster memory; that's what **ResourceQuota** and **LimitRange** per namespace enforce. Define them early, not after an outage.

---

## Networking model

Kubernetes mandates a **flat network**: every pod can reach every other pod by IP, regardless of node. This is implemented by a **CNI plugin** (Calico, Cilium, Flannel). k3s ships Flannel by default; Calico/Cilium add NetworkPolicy enforcement and richer features.

> **Why this matters for security (doc 14)** — flat networking means a compromised pod can reach *every* other pod by default. **NetworkPolicies** are how you carve the flat network into zones. By default, if no policy selects a pod, all traffic is allowed. The moment one policy selects it, everything not explicitly allowed is denied. This default-allow-until-selected behavior is a classic gotcha.

### DNS

CoreDNS provides cluster DNS. Services get `<service>.<namespace>.svc.cluster.local`. This is how Outline reaches `postgres.database.svc.cluster.local`.

---

## Debugging: the systematic method

Never guess. Follow the funnel:

```
kubectl get pods -n <ns>            # what's the phase? (Pending/Running/CrashLoop/...)
kubectl describe pod <pod> -n <ns>  # events at the bottom — 90% of answers are here
kubectl logs <pod> -n <ns>          # app's own output
kubectl logs <pod> --previous       # logs from the crashed container
kubectl exec -it <pod> -- sh        # get inside
kubectl get events -n <ns> --sort-by=.lastTimestamp
```

Map the symptom to the layer:

| Symptom | Likely layer | First command |
|---|---|---|
| `Pending` | Scheduling | `describe pod` → look at the Events |
| `ImagePullBackOff` | Registry/auth | Check image name + `imagePullSecrets` |
| `CrashLoopBackOff` | App | `logs --previous` |
| `ContainerCreating` forever | Volume/mount | `describe pod` → volume events |
| `OOMKilled` | Limits | `describe pod` → raise memory limit |
| Service not reachable | Networking/selector | `kubectl get endpoints <svc>` |
| Ingress 404/503 | Ingress rules | `describe ingress` + controller logs |

> **Senior lens** — `kubectl get endpoints <service>` is the most underused command. If a Service has no endpoints, its selector matches no ready pods — so the problem is upstream of networking. Always check endpoints before blaming the network.

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| replicas | Never 1 for anything user-facing; ≥2 for HA, ≥3 if you want to survive a zone/node loss |
| requests/limits | Set requests from observed p99 usage, not guesswork; databases → Guaranteed QoS |
| PDB | Required for any multi-replica workload; prevents drain-time outages |
| StatefulSet vs Deployment | StatefulSet whenever pod identity or per-pod storage matters |
| RWO vs RWX | RWO for single-writer DBs; RWX only if the storage backend truly supports it |
| Namespaces | One per logical service; pair with ResourceQuota from day one |
| CNI | Flannel for simplicity; Cilium/Calico when you need NetworkPolicy enforcement |

---

## Failure modes you must deliberately cause

1. **Delete a pod** in a 3-replica Deployment → watch it respawn. The reconciliation loop in action.
2. **Set an impossible request** (e.g. 100Gi memory) → pod goes `Pending`; read the scheduler's reason.
3. **Cordon + drain a node** with a PDB → watch pods reschedule while the PDB holds the line.
4. **Break an image tag** → `ImagePullBackOff`; understand the difference from `CrashLoopBackOff`.
5. **Fill node memory** → watch QoS eviction order (BestEffort dies first).
6. **Point a Service at the wrong selector** → endpoints go empty; service silently black-holes.

---

## Exit criteria for M2

- [ ] You can explain every control-plane component and what happens when one dies
- [ ] You can deploy a stateless app with 3 replicas, a Service, and an Ingress with TLS
- [ ] You've intentionally caused and diagnosed each symptom in the table above
- [ ] You understand the difference between a PV, a PVC, and a StorageClass
- [ ] You can drain a node safely using a PDB
- [ ] Namespaces defined with ResourceQuotas

Next: `03-helm-packaging` — turning all this YAML into something reusable and versioned.
