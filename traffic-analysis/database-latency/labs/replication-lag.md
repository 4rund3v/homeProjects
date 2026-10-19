# Lab: add a read replica, drive load, read the lag

A stretch goal. Skip if time is short — the signature is the same as `project/labs/break-the-system.md` break 3 (slow PVC).

## Step 1 — add the replica

A second `bitnami/postgresql` deployment in `shop` ns, configured as a streaming replica of the primary. Point its `PG_REPL_PORT` at the primary's `5432`. The primary's `pg_hba` must allow `replication` from the replica's pod IP range.

```
kubectl -n shop get pods
```

Two PG pods now. The exporter on the replica scrapes `pg_stat_wal_receiver`.

## Step 2 — drive write load

Point the app's *writes* at the primary, *reads* at the replica. Generate writes:

```
k6 run -usages examples/load-test/k6-writes.js
```

## Step 3 — read the lag

```
# WAL bytes lag on the replica
pg_stat_wal_receiver_wal_bytes_received - pg_stat_wal_receiver_wal_bytes_replayed
```

Under a write burst, the gap grows. It shrinks as the replica catches up. The *shape* (grow during burst, shrink after) is the signature of a healthy streaming replica.

A *flat, growing* gap (never shrinks) means the replica cannot keep up — either the primary is producing WAL faster than the replica can replay, or the network between them is saturated.

## Step 4 — read on the replica, observe staleness

The app reads `products` from the replica. During a write burst, the replica is N seconds behind. The app returns data from N seconds ago. The customer sees "I just updated my order, it is not showing."

The fix is not "make the replica faster." The fix is `readYourOwnWrites` on the app — write to the primary, read *that specific user's* data from the primary.

## Question

What is the *alert* on replication lag? (A threshold on `pg_stat_wal_receiver_wal_bytes_received - ...replayed`, in bytes, for 5 m. Not a mean. Not a rate. A *gap* that is growing.)
