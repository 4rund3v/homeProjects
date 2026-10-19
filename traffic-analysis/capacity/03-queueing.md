# 03 — Where the latency goes when the system saturates

When the system is past the knee, the extra latency is not in the *work* — it is in the *queue*. The queue is the senior engineer's first suspect.

## The three queues in this project

1. **The app's DB pool queue.** Requests wait for a free connection. Queue time = `pool_in_use` pinned at `pool_max` and `pool_idle` = 0. The *work* (the DB query) is fast; the *wait* is slow.
2. **NGINX's worker-connection queue.** Past `worker_connections`, new requests wait for a free worker. The queue is in the L7 layer, not the app.
3. **The PVC's I/O queue.** Past the disk's IOPS, reads/writes wait for a free I/O slot. The queue is in the kernel, not the app.

## How to tell which queue

Each queue has a *distinct* signal:

| Queue | Signal | What it looks like |
|---|---|---|
| App pool | `pool_in_use` / `pool_idle` | `in_use` pinned, `idle` = 0. DB `mean_exec_time` *flat*. App p99 *cliff*. |
| NGINX worker | `nginx_ingress_controller_connections_active` | Pinned at `worker_connections`. App p99 *cliff*, but the *gap* between app p99 and DB mean is *small* (the queue is *before* the app). |
| PVC I/O | `node_disk_io_time_seconds_total` rate, `node_disk_reads_awaiting` | `awaiting` climbs. *Every* query is slow (not just the tail), because the disk is the shared resource. |

The *location* of the queue changes the signature. A pool-queue shows up as a *gap* between app p99 and DB mean. A disk-queue shows up as *all* DB queries being slow, not just the tail. A NGINX-queue shows up as a *gap* between NGINX p99 and app p99.

## The rule

When p99 climbs a cliff, *first* ask: **is the *work* slow, or is the *wait* slow?**

- Work slow: `mean_exec_time` / the CPU-bound work is up. The resource itself is the bottleneck. Fix the work (index, code, bigger node).
- Wait slow: `mean_exec_time` is *flat*, but p99 is a cliff. The *queue* is the bottleneck. Fix the queue (bigger pool, more workers, faster disk).

The two fixes are *opposite*. A pool-saturation fix is "raise the pool." A CPU-saturation fix is "reduce the work per request." If you confuse the two, you raise the pool on a CPU-bound system (no help) or reduce the work on a pool-bound system (helps, but you did not need to — a bigger pool would have fixed it faster).

## The lab

`capacity/labs/pool-full.md` isolates the *pool* queue: it pins the pool and shows the *gap* between app p99 and DB mean. `project/labs/break-the-system.md` break 3 (slow PVC) isolates the *disk* queue: it shows *all* DB queries slow, not just the tail. Compare the two signatures.

## The Little's-law tie-in

The queue *is* the `L` in `L = λW`. As λ climbs past the knee, W climbs (because the queue grows), so L grows *faster* than λ. The L curve is convex past the knee. The pool is pinned because `L` has hit `L_max` (the pool size). The system is *full*.

That is the whole theory in one line: **past the knee, you are not paying for the work, you are paying for the queue.** The senior engineer sizes the queue (the pool, the workers, the I/O depth) to hold the `L` at the expected λ. If `L(λ_expected) > L_max`, the system is undersized.
