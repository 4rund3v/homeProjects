# 13 — Node Health: The Machines Under Everything

**Folder:** `13-node-health/`
**Milestone:** M12 — Node health

---

## Teach first: the node is a Linux box, and Linux fails in known ways

Kubernetes abstracts pods, but it cannot abstract away the machine. Nodes fail in patterns that Kubernetes itself is *bad at seeing*, because the kubelet — the thing reporting node status — runs on the failing node. When the disk fills or the kernel wedges, the kubelet's own reports degrade or stop.

So node health is its own discipline, with its own tools:

| Symptom | Kubernetes sees | What actually happened |
|---|---|---|
| Disk full | pods fail with `Evicted`, writes fail | filesystem hit 100% — logs, images, or empty space reserved |
| Memory pressure | evictions, OOM kills | cgroups + page cache squeezed real memory |
| Kernel/net issues | nothing, or flaky everything | conntrack table full, NIC errors, soft lockups |
| Clock drift | TLS failures, cert errors "randomly" | NTP stopped; certs not-yet-valid/already-expired |
| Disk I/O degradation | "everything is slow," no errors | dying disk, IO wait — *the* silent killer |

The lesson: **alerts on pod symptoms arrive late and ambiguous; alerts on node resources arrive early and precise.** Instrument the machine directly.

---

## The toolchain

| Tool | Role |
|---|---|
| **node-exporter** (DaemonSet) | exports CPU/mem/disk/network/FS metrics per node → Prometheus (doc 11) |
| **node-problem-detector** (NPD, DaemonSet) | detects *kernel-level* problems the kubelet can't report, surfaces them as Node Conditions/Events |
| **kubelet/cAdvisor metrics** | per-pod resource usage (`kubectl top` comes from here) |
| **SMART monitoring** (node-exporter textfile or smartctl exporter) | physical disk health — predictive, not reactive |

### node-exporter — the metrics

The queries you'll actually use (Prometheus, doc 11):

```promql
# disk utilization per mountpoint — alert at 80%
(1 - node_filesystem_avail_bytes{mountpoint!~"/proc.*"}
    / node_filesystem_size_bytes{mountpoint!~"/proc.*"}) * 100

# disk fill *rate* — "will fill in <4h" prediction
predict_linear(node_filesystem_avail_bytes[1h], 4*3600) < 0

# memory: available (not "free" — cache is reclaimable!)
node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes

# CPU iowait — the silent-killer detector
rate(node_cpu_seconds_total{mode="iowait"}[5m]) * 100

# network errors
rate(node_network_receive_errs_total[5m])
```

> **Senior lens — `MemAvailable`, never `MemFree`.** Linux uses free memory for page cache; `MemFree` low is *healthy*. `MemAvailable` is what the kernel estimates is actually usable. Dashboards alerting on `MemFree` page constantly for no reason — the classic rookie dashboard bug.

> **Threshold — the 80/90 disk rule has a reason.** Ext4 reserves ~5% for root; some databases refuse writes well before 100%; and the doc 06 rule (Postgres needs ~2× headroom for WAL/vacuum) makes 80% *already dangerous* for DB volumes. 80% = page (action: clean/grow), 90% = urgent (something breaks imminently). Combined with `predict_linear`, you catch "filling at a rate that reaches 100% overnight" *today*.

### node-problem-detector — what the kubelet can't say

NPD watches kernel logs (dmesg/journald) for host-level trouble and reports them as **Node Conditions**:

- `KernelDeadlock`
- `ReadonlyFilesystem` (ext4 flips RO on errors — instantly fatal for writes)
- `FrequentKubeletRestart`, `FrequentDockerRestart`
- OOM events, network trouble

> **The reporting path (the mechanism "reports as a Node Condition" hides):** NPD runs a DaemonSet that *reads* the node's dmesg/journald and runs its own checkers. When a checker fires, NPD **patches `node.status.conditions`** on the Node object *through the API* (it has a ServiceAccount with that permission) — it does *not* wait for the kubelet, which on a failing host is itself degraded or silent. Two consequences a cold reader must know: (1) the *source* is NPD's checker config (`config.json` with custom checkers; the defaults `KernelDeadlock`, `ReadonlyFilesystem`, `FrequentDockerRestart` are baked into the standard config and are keyed to *which* runtime you run — a cAdvisor/containerd node won't emit `FrequentDockerRestart` at all, so a condition that "never exists on your setup" is usually just a checker that doesn't match your runtime, not a missing failure). (2) NPD emits both a **Condition** (a sticky state, survives) *and* a **k8s Event** (transient, ~1h TTL) — alert on the *condition* for persistence, use the *event* for "when did it first happen." The metric `kube_node_status_condition` that the PromQL below queries is provided by **kube-state-metrics** (doc 11) translating that Condition into a number — NPD writes the Condition, kube-state-metrics scrapes it into a series.

Without NPD, a node with a readonly filesystem shows up only as pods mysteriously failing writes. With NPD it's a Node Condition you can alert on — and a condition your automation can react to (cordon the node).

```promql
# alert on NPD conditions
kube_node_status_condition{condition="ReadonlyFilesystem",status="true"} == 1
```

---

## Kubernetes's own node lifecycle machinery

Know these — they *are* node health, from the control plane's side:

- **Conditions** — `Ready`, `DiskPressure`, `MemoryPressure`, `PIDPressure` — kubelet-reported states.
- **Taints by eviction manager** — under DiskPressure/MemoryPressure the kubelet evicts pods (BestEffort first — doc 02's QoS) and taints the node.
- **Node Controller** — if a node stops heartbeating, it's marked `NotReady`; pods get evicted after `pod-eviction-timeout` (default 5m).
- **Cordon/drain** — the *voluntary* version: you take a node out before maintenance.

```bash
kubectl cordon node2          # no new pods schedule here
kubectl drain node2 --ignore-daemonsets --delete-emptydir-data   # evict workloads safely (PDBs hold the line — doc 02)
kubectl uncordon node2
```

> **Failure mode — the evicted-pod mystery.** Pods evicted with `Evicted` status are the kubelet saying "this node is under DiskPressure/MemoryPressure." Juniors debug the pod; seniors check `kubectl describe node` (Conditions + allocated resources) and node-exporter. **Always read `kubectl describe node` before debugging pods that were evicted.**

---

## Node maintenance, as a practiced procedure

This is a day-2 skill Jenkins/CD can't give you. The drill (repeat until boring):

1. `kubectl drain <node> --ignore-daemonsets` — PDBs (docs 02, 10) keep services up; watch pods reschedule.
2. Watch: Postgres stays quorum (doc 06), Outline stays ready (doc 10), alerts stay quiet.
3. Do the maintenance (kernel update, disk swap).
4. `kubectl uncordon <node>`; watch the scheduler rebalance.

> **Tradeoff — one node at a time, always.** Draining two of three nodes simultaneously breaks etcd quorum (doc 01's threshold) *and* Postgres quorum (doc 06). A "rolling restart of the fleet" that doesn't respect quorum math is an outage you scheduled yourself.

---

## The physical layer — homelab-specific

Bare metal gives you failures cloud abstracts away. Worth wiring up:

- **SMART** (`smartctl -a /dev/sdX`, or the smartctl exporter) — reallocated sectors climbing = replace the disk *now*, not when it dies.
- **Temperature** — node-exporter's thermal zone metrics; a fan failure presents as "mysterious throttling."
- **Power** — a UPS with NUT; the real question is graceful shutdown ordering (etcd and Postgres shut down *last*... actually first in shutdown, last in boot — think it through once).

> **Senior lens — the boot-order question.** After full-power-loss: do your StatefulSets (Postgres, Redis, MinIO) come up before the apps that need them? Kubernetes starts everything it can, concurrently. Readiness probes + CrashLoopBackOff retries eventually converge, but a 5-minute Postgres startup (WAL replay) with Outline crashlooping is noisy and slow. Options: `initContainers` that wait for dependencies, or simply accept the retry loop with sane probe timings (doc 10). Know which behavior your manifests have — watch one full cold boot at least once.

---

## Capacity planning — from metrics to decisions

Node health includes *future* health. The planning loop:

1. **Measure**: per-node allocatable vs. requests (scheduling view) and actual usage (node-exporter view).
2. **Track headroom**: if requests sum to >70% of a node's allocatable, scheduling gets brittle (big pods go Pending).
3. **Project**: `predict_linear` on disk; simple trend on memory (leak detection — a line that only goes up over weeks is a leak, no matter how slow).

```promql
# cluster-wide requested vs allocatable CPU
sum(kube_pod_container_resource_requests{resource="cpu"})
  / sum(kube_node_status_allocatable{resource="cpu"})

# a pod's memory trend over 7d (leak detector)
max_over_time(container_memory_working_set_bytes{pod="outline-server-0"}[7d])
```

> **Threshold — the 70% rule.** Cluster requests above ~70% of allocatable = new pods start going Pending unpredictably; above 85% you're doing scheduled downtime with every rollout. Alert on it like disk.

---

## Thresholds and tradeoffs summary

| Signal | Page | Urgent |
|---|---|---|
| Node disk | > 80% | > 90% or fill-in-<4h predicted |
| MemAvailable | < 10% sustained | < 5% |
| NPD conditions | any (KernelDeadlock, ReadonlyFS) | — |
| Node NotReady | any | > 5m |
| Disk I/O | iowait > 20% sustained 15m | SMART climbing |
| Cluster requests/allocatable | > 70% | > 85% |

---

## Failure modes you must deliberately cause

1. **Fill a node disk** (write a big file to `/var/lib/docker` on the node) → watch DiskPressure taint, evictions, your 80% alert firing *first*. This is the drill that makes the alerts real.
2. **Memory bomb a node** (`stress-ng` or a BestEffort pod ballooning) → observe QoS eviction order from doc 02.
3. **Stop NTP on a node** → watch clock drift break TLS with "certificate not yet valid" — the most confusing error in distributed systems until you've seen it once.
4. **Drain a node** (with and without PDBs on workloads) → see the difference.
5. **Pull a disk / mark a disk failing** (VM-level: throttle its I/O) → iowait climbs, latency follows; see which dashboard catches it first.
6. **Full cluster cold boot** → watch boot-order behavior; note anything that needed manual kicks.

---

## Exit criteria for M12

- [ ] node-exporter + NPD on every node, scraped by Prometheus
- [ ] Disk (80/90 + predict_linear), memory (MemAvailable), iowait, node-NotReady alerts live and *fired at least once each in a drill*
- [ ] `kubectl describe node` is reflex for evicted-pod debugging
- [ ] Drain/uncordon performed cleanly on a live cluster with PDBs holding
- [ ] SMART or equivalent physical-disk signal monitored on bare metal
- [ ] Requests/allocatable tracked; a capacity decision made from data

Next: `14-security-hardening` — locking it all down.
