# Operations — Running This in Production

This file is the operational companion to the design and infrastructure docs. It covers health checks, graceful shutdown, scaling, backup and restore, alerting, and the runbooks that turn an alert into a procedure. It is written as though the system is live and you are the one carrying the pager.

---

## The Operating Philosophy

The system is designed so that failures degrade it rather than break it. A dependency outage makes it less useful, not more broken: the cache fails and reads hit the database; the broker fails and traces queue locally; the scan service fails and the trace endpoint reports degraded rather than hanging. Your job as an operator is to notice the degradation before users do, which means the observability has to be trustworthy and the alerts have to have runbooks.

The order of investigation is always the same: **trace, then metrics, then logs.** The trace tells you where time went and which hop failed. The metrics tell you whether the failure is widespread or isolated. The logs give you the specifics, but you should already know what you are looking for by the time you open them. Reading logs first is the junior instinct; it works on small systems and fails at scale.

---

## Health Checks

Three layers, each answering a different question.

**Liveness** — is the process alive? A dedicated endpoint that does nothing but confirm the process is running. If it fails, the container restarts. It must not check dependencies, because restarting a process does not fix a database outage, and a liveness check that fails during a dependency outage produces a restart loop that makes everything worse.

**Readiness** — can this instance serve traffic? This endpoint checks the process *and* its critical dependencies: the database connection, the cache connection, and the broker connection. If any fail, the instance is removed from the load balancer's rotation but is not restarted. When the dependency recovers, the instance rejoins rotation automatically. This is what lets a database failover happen without returning errors to users.

**Deep health** — is the system healthy overall? An endpoint that reports the status of every component: each consumer's lag, the stream processor's state, the cache hit rate, the database connection pool utilization. This is what a dashboard reads, not what a load balancer reads. It is for humans and for monitoring.

**The distinction that matters:** liveness restarts, readiness routes. Confusing them is one of the most common causes of self-inflicted outages. A process with a full connection pool is not dead — restarting it drops every in-flight request. A process that cannot reach the database is not dead either — restarting it just delays the inevitable. Only restart when the process itself is wedged.

---

## Graceful Shutdown

Every component handles the termination signal the same way: stop accepting new work, finish the work in flight, then exit.

**The HTTP handler:** on signal, stop accepting new connections, wait for in-flight requests to complete up to the grace period, then exit. The pre-shutdown hook in the deployment adds a delay before the signal so the load balancer removes the pod from rotation first. Without that delay, requests arrive at a pod that is already shutting down and are dropped.

**The WebSocket holder:** on signal, stop accepting new connections, send a close frame to connected clients so their reconnection logic fires immediately rather than waiting for a timeout, drain, then exit. The long grace period exists because draining thousands of connections takes time.

**The Celery worker:** on signal, stop picking up new tasks, finish the current task, commit any pending offsets, then exit. A task interrupted mid-write is safe because the offset is not committed until the write succeeds, so the message is redelivered.

**The ingestion consumer:** the most delicate. It must commit its offset only after the database write succeeds. If it is killed between the write and the commit, the message is redelivered and the idempotency key absorbs the duplicate. If it commits before the write, a crash loses the message. The ordering is not negotiable.

**The stream processor:** on signal, checkpoint its window state to disk before exiting. Without the checkpoint, the in-progress window is lost and the materialized view has a gap.

---

## Scaling — Which Component, When, and Why

Each component has a different scaling trigger, and using the wrong one wastes money or fails to help.

**The HTTP handler scales on CPU.** It is stateless and request-bound. Add replicas when the ninety-fifth percentile latency rises or CPU crosses the target. The autoscaler handles this automatically.

**The Celery worker scales on queue depth, not CPU.** The work is I/O-bound — waiting on the scan, waiting on the database — so CPU stays low even when the queue is backing up. Watch the queue length; add workers when it grows and does not drain.

**The ingestion consumer scales on lag.** Consumer lag is the gap between the newest message in the topic and the last one this group processed. Lag above the target means the consumer cannot keep up. Add replicas up to the partition count; beyond that, extra consumers sit idle because there are no partitions left to assign.

**The stream processor does not scale past the partition count**, for the same reason. It also cannot scale on CPU, because the window state is local to each instance. Scaling it redistributes partitions and forces state rebalancing, which is expensive.

**The WebSocket holder does not autoscale at all.** Each replica holds its own connections; adding a replica does not relieve the others. It scales on connection count, manually, and it carries a disruption budget so scaling down does not drop everyone.

**The Go service scales on network segments, not load.** Each instance scans the local network it is attached to. One replica per node, co-located with the segment it scans. You cannot put it behind a load balancer, because each instance sees a different network. This is the case where the stateless scaling model simply does not apply.

**The database scales vertically first, then with read replicas.** Writes go to the primary. Reads that tolerate slight staleness — the dashboard's recent-device list, for instance — can go to a replica. The cache absorbs most read traffic before it reaches either.

---

## Backup and Restore

**What is backed up:** the PostgreSQL database. Everything else is reconstructible — the cache regenerates, the broker queue re-fills from re-triggered traces, the Kafka log is a transport whose contents are derived from scans, the certificates re-issue, the secrets live in the secret manager.

**Schedule:** a logical dump every six hours to deduplicating object storage. A dump is portable across PostgreSQL versions, unlike a raw filesystem copy, which ties you to the exact version and layout.

**Retention:** seven daily, four weekly, twelve monthly. This satisfies the three-copy, two-media, one-offsite rule: the live database, the most recent dump, and the object storage copy, with the offsite copy in a different region.

**Encryption:** dumps are encrypted before upload. A database dump contains MAC addresses, IP addresses, hostnames, and user records. It is sensitive.

**Restore procedure, and why it is rehearsed:**
1. Provision a scratch database.
2. Restore the chosen dump into it.
3. Verify row counts against the expected figures for that backup's timestamp.
4. Spot-check specific devices against the dashboard's history.
5. Only then restore into production, during a maintenance window, with traffic drained.

A backup you have never restored from is not a backup — it is a hope. The restore is rehearsed quarterly against scratch, and the rehearsal is logged. The first time you restore should never be during an incident.

---

## Alerting

Every alert has three parts: a condition, a severity, and a runbook link. An alert without a runbook is noise, because it pages someone who then has to figure out what to do from scratch, under pressure, in the middle of the night. A runbook is what makes an alert a tool instead of a training exercise in ignoring pages.

**Severity levels:**
- **Page** — user-visible impact or imminent data loss. Wake someone up.
- **Ticket** — degradation without current user impact, or a leading indicator. Handle during business hours.
- **Log** — informational. No action, but retained for correlation.

**The alerts this system ships with:**

*Trace success rate below target* — page. Traces are the core function; a drop means users cannot discover devices. The runbook walks from the failure metric to the specific failing component.

*Trace latency at the ninety-fifth percentile above target* — ticket first, page if it worsens. Usually the scan service is slow because the subnet is larger than expected or a discovery mechanism is timing out.

*Consumer lag above threshold* — page if growing, ticket if stable. A stable lag means the consumer is slow but keeping pace with arrival; a growing lag means it is falling behind and will never catch up.

*Cache hit rate below target* — ticket. Either the invalidation is too aggressive, evicting entries before they are read, or the traffic pattern changed. Not user-visible immediately, but it foreshadows database load.

*API latency at the ninety-fifth percentile above target* — page if above the error budget, ticket otherwise. The runbook checks the database first (missing index, long query, connection pool exhaustion), then the cache.

*Task failure rate above threshold* — page. Failed tasks mean traces are not completing. The runbook checks the failure reason in the task result store, then the Go service's health.

*Database connection pool near exhaustion* — page. The next request that needs a connection will block, then time out. Usually a leak or an undersized pool.

*Cache memory near limit* — ticket. Approaching the eviction threshold means the hit rate is about to drop. Either raise the limit or investigate what is being cached.

*Certificate expiry within two weeks* — page. Auto-renewal has failed silently. A expired certificate takes down TLS for the affected service, and the failure is total and immediate.

*Backup job failure* — page. A silent backup failure means you have no recovery point. This is the alert people ignore and then regret.

---

## Runbook Structure

Every runbook follows the same shape, so an on-call engineer can navigate any of them under pressure:

1. **What this alert means** — one paragraph, plain language, no jargon.
2. **User impact** — who is affected and how. This determines urgency.
3. **Where to look first** — the specific trace, metric, or dashboard, in order. Never "check the logs."
4. **Common causes and their fixes** — ordered by likelihood, each with a concrete action.
5. **Escalation** — who to page if the documented causes do not apply, and what information to bring them.
6. **Post-incident** — what to record for the post-mortem, so the next occurrence is faster.

**Example shape — consumer lag:**

*Meaning:* the ingestion consumer is falling behind the producer. Findings are being produced to Kafka faster than they are being written to the database.

*Impact:* the dashboard lags behind reality. Devices found in the last few minutes may not appear until the consumer catches up. No data loss — Kafka retains the messages.

*Look first:* the consumer lag metric per partition. Is it growing or stable? Then the consumer pods — are they all running? Then the database — is write latency elevated?

*Causes, in order:* a consumer pod crashed or is stuck (restart it); the database is slow, so each write takes longer (check for a long-running query or a lock); the arrival rate spiked, for instance because a scheduled trace ran on a large subnet (add consumers up to the partition count); the consumer has a bug causing it to process slowly (check the failure metric and recent deploys).

*Escalation:* if lag is growing and none of the above applies, page the data platform owner with the lag figure, the partition distribution, and the database latency.

*Post-incident:* record the peak lag, the duration, and the root cause. If the cause was arrival rate, consider whether the trace schedule needs staggering.

---

## Deploy and Rollback

**Deploy:**
1. Render and review the chart diff. Know what is changing before it changes.
2. Apply the upgrade with a rollout timeout.
3. Watch the rollout status until every pod is ready.
4. Verify the deep health endpoint reports all components healthy.
5. Watch the error rate and latency metrics for a defined observation window.
6. If anything regresses, roll back immediately. Investigate after stability is restored, not during.

**Rollback:**
1. Revert to the previous release revision.
2. Watch the rollout complete.
3. Verify health and metrics return to baseline.
4. Then, and only then, open the investigation.

**The rule:** restore service first, understand second. An investigation conducted while users are impacted is slower, not faster, because you are working under pressure and guessing. Stability buys you the time to diagnose properly.

**Why the observation window matters:** a deploy that looks fine for thirty seconds can regress at minute five, when a cache expires or a window closes. The window is defined per change, based on what could plausibly break.

---

## Common Failure Scenarios and the Designed Response

**Kafka unavailable.** The trace endpoint still accepts requests and enqueues tasks. The Celery worker runs the scan but cannot produce findings. Findings are held locally and flushed when the broker returns, or the task fails and is retried with backoff. The dashboard shows a degraded status. This is graceful degradation by design — the failure is visible and bounded.

**Redis unavailable.** Cache reads fall through to the database. The Celery broker is unavailable, so new traces cannot be enqueued — the endpoint returns a service-unavailable response rather than accepting work it cannot queue. Pub/sub is unavailable, so the dashboard stops receiving pushes and clients reconnect until it returns. The cache hit rate metric drops to zero, which is your signal.

**Database unavailable.** Readiness checks fail, pods are removed from rotation, the load balancer returns errors rather than routing to pods that cannot serve. The consumer stops committing offsets, so no messages are lost. When the database returns, readiness passes, pods rejoin, and the consumer catches up. This is why readiness must check the database.

**Go service unavailable.** Trace tasks fail after their retry budget. The endpoint reports the failure. The rest of the system is unaffected — no devices are ingested, but nothing else breaks. The Go service is restarted by its liveness probe or its supervisor.

**A single consumer pod crashes.** Its partitions are reassigned to the remaining consumers in the group. Processing continues, slower. The uncommitted messages are redelivered to the new owner, and the idempotency key absorbs any duplicates from a partially completed write. No operator action is required beyond noticing the restart.

**A node is drained.** The disruption budget prevents the WebSocket holder from being fully evicted. Connections on the drained node drop, and clients reconnect to surviving replicas. The database StatefulSet's pod reschedules and remounts its volume. Data survives.

**A certificate expires.** TLS fails for the affected service. Connections are refused. This is total and immediate, which is why the expiry alert pages two weeks out — auto-renewal failing silently is otherwise invisible until the moment it is catastrophic.

---

## The Post-Mortem

Every page gets a written post-mortem, blameless, within three business days. The template:

1. **Timeline** — when it started, when it was detected, when it was mitigated, when it was resolved. Detection time is the most important number; it is the one you can improve cheapest.
2. **Impact** — who was affected and how. Quantify it.
3. **Root cause** — the actual mechanism, not the proximate trigger. "The database ran out of connections" is a trigger; "the pool was sized for the old arrival rate and nobody revisited it after the trace schedule changed" is a root cause.
4. **What went well** — including detection that worked and degradation that held.
5. **What went poorly** — including detection that failed and anything that made recovery slower.
6. **Action items** — each with an owner and a date. An action item without an owner is a wish.

**The metric that matters most:** time to detect. Every other number — time to mitigate, time to resolve — is downstream of knowing something is wrong. This is why the observability phase is not optional polish. It is the system's ability to tell you it is failing, and a system that cannot tell you it is failing will fail silently until users notice.
