# 01 — RED and USE: the two triage frameworks

## RED (for a *request-driven* service, like the app)

For every service that handles requests, three metrics:

- **R**ate — `sum(rate(http_request_duration_seconds_count[5m]))`. How many requests per second.
- **E**rrors — `sum(rate(http_request_duration_seconds_count{status=~"5.."}[5m]))`. How many are failing.
- **D**uration — `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))`. How slow is the 95th percentile.

One dashboard row, three panels. If any of the three is off its baseline, the service is in trouble. The shape of *which one* is off tells you *what kind* of trouble:

- Rate up, errors flat, duration up → **load** problem. The service is being hit harder than it is built for.
- Rate flat, errors up, duration up → **bug** problem. A code path is failing.
- Rate flat, errors flat, duration up → **dependency** problem. The DB is slow, not the service.

## USE (for a *resource*, like the node or the DB)

For every resource (CPU, memory, disk, network, DB connections):

- **U**tilization — how much of the resource is in use, as a fraction. `node_cpu_seconds_total` → fraction of 1.0 per core.
- **S**aturation — how much work is *queued* waiting for the resource. CPU: run-queue length. Disk: I/O queue. DB: connection pool wait.
- **E**rrors — how many operations on the resource failed. Disk I/O errors. DB query errors.

The senior-engineer habit: **saturation is the leading indicator.** Utilization can be 70% and the resource is fine. Saturation > 0 means work is queuing, and the tail latency is about to move. Watch the queue, not the fraction.

## The two together

When the app's RED shows "duration up," the next question is *which resource is saturated*. That is a USE question:

- CPU run-queue on the node?
- Disk I/O queue on the PVC?
- DB pool queue in the app?

The RED panel tells you *that* the service is slow. The USE panel tells you *why*. Read them in that order, not the other way.

## A concrete triage flow

1. App RED: duration up.
2. App RED: errors flat. → Not a bug, not a failure. A *slowness* problem.
3. Node USE: CPU utilization 80%, run-queue 2. → The node is CPU-bound.
4. Pod-level: `kube_pod_container_cpu_usage:sum` for the app is 3.5 cores out of a 4-core node. → The app is the CPU hog.
5. Fix: scale the app, or reduce its CPU, or move it to a bigger node.

Every step is a *panel*. No step is a log grep. Logs enter at step 4, to find *which* code path is burning CPU.
