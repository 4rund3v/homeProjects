# 03 — Replication lag and reads-on-replica

This project starts with a *standalone* Postgres. The replication-lag lab is a stretch goal: add a read replica and watch the lag.

## How lag works

The primary writes WAL (Write-Ahead Log). The replica streams the WAL and replays it. Lag = time between a commit on the primary and the replay of that commit on the replica.

Under normal load, lag is < 1 s. Under a write burst (a big migration, a batch job), lag can be minutes. A read-on-replica during that window returns *stale data*.

## The metrics

On the primary:

```
pg_stat_replication{client_addr, application_name, state, sync_state, lag}
```

On the replica:

```
pg_stat_wal_receiver{status, sender_host, sender_port, lag}
```

The exporter surfaces these. The `lag` is in bytes (WAL position), not seconds. Convert:

```
# WAL lag in bytes
pg_stat_replication_wal_bytes_received - pg_stat_replication_wal_bytes_replayed
```

A sustained lag of > 10 MB is a warning. A sustained lag of > 100 MB is an incident.

## The failure mode you will measure

1. Add a replica (a second PG pod, streaming from the primary).
2. Drive write load on the primary.
3. Read from the replica.
4. Watch `pg_stat_wal_receiver_lag` grow.
5. The read returns data from N seconds ago. The app does not know. The *customer* sees stale data.

## The senior-engineer rule

If the app's correctness depends on "I just wrote this, I should be able to read it," the app *must* read from the primary. Read-on-replica is a *scaling* optimization, not a *correctness* mechanism. The app's write path must have a `readYourOwnWrites` flag.

The alert on lag:

```
pg_stat_replication_lag_bytes > 10_000_000 for 5m
```

Not on a mean. On a *threshold* of a *count* of bytes.

## The lab

`database-latency/labs/replication-lag.md` adds a replica, drives load, and reads the lag panel.
