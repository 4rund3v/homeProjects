# Lab: break the p99, keep the p50 flat

The signature of a queueing system under saturation is: p50 stays roughly flat, p99 climbs a cliff. Build it deliberately.

## Prereqs

- App + DB up.
- `k6` or `ab` available on the host.

## Scenario A: DB pool saturation

Set the app pool to 4 connections. Load 200 VU.

Watch:
- App p50 — should stay near idle (most requests complete before the pool is saturated).
- App p99 — should be orders of magnitude higher than p50.
- `pg_stat_activity_numbackends` — pinned at 4.
- New requests queue in the app's pool — that queue time is what p99 measures.

**Question:** the p99 is *queue time*, not *query time*. How do you tell from the panels? (`pg_stat_statements_mean_exec_time` stays near idle; the gap between app p99 and DB mean is the queue.)

## Scenario B: slow PVC

Pause the Postgres pod, then resume it (or `dd` a big file on the PVC as in `project/labs/break-the-system.md`).

Watch:
- App p50 — rises slowly, then flat.
- App p99 — rises fast, then flat.
- `pg_stat_statements_mean_exec_time` — rises across the board, not just the tail.

**Question:** why does p50 *also* rise here, unlike scenario A? (Disk I/O slows *every* query, not just the ones that hit a hot row or a lock. There is no queue to hide it in.)

## Scenario C: slow code path on one endpoint

Patch `/api/orders` to sleep 500 ms. Leave `/api/products` alone.

Watch:
- `/api/orders` p50 — jumps 500 ms.
- `/api/orders` p99 — jumps more than p50 (the sleep is constant, but the DB call on top of it adds a tail).
- `/api/products` p50/p99 — flat.
- NGINX p95 — mixed, because it sees both endpoints.

**Question:** which panel would have caught a 500 ms sleep *before* customers complained? (The per-endpoint p50. The endpoint-mixed p95 would not move much — the endpoint-mixed p99 might move a little. Per-endpoint is the only reliable view.)

## Restore

```
kubectl -n shop rollout undo deploy/shop-api
```

Re-run the baseline. All percentiles should return to the idle shape.
