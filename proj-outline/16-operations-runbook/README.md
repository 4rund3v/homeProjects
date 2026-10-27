# 16 — Operations Runbook: Day-2 and Beyond

**Folder:** `16-operations-runbook/`
**Milestone:** M15 — Runbook

---

## Teach first: day 1 vs. day 2

Day 1 is *building* the platform — docs 01–14. Day 2 is *operating* it: the daily/weekly/monthly habits, the debugging sessions, the incidents, the upgrades. **Day 2 is the overwhelming majority of a system's life** — a build that takes a month typically operates for *years* — so the operational skill is where your time actually goes.

The difference between a junior and a senior in operations isn't knowledge of tools — it's the presence of:

1. **Runbooks** — written procedures for known failure modes, so the 3am version of you doesn't have to improvise.
2. **Debugging method** — a systematic funnel from symptom to root cause, not guess-and-check.
3. **Change discipline** — small changes, observed effects, easy rollback.
4. **Blameless postmortems** — every incident makes the system measurably better or it was wasted pain.

This doc is the capstone: the operating manual for everything docs 01–15 built, and the habits of the engineer who runs it.

---

## The runbook format (and why it matters)

Every alert you configured in docs 11–13 should eventually point at a runbook entry. Format:

```markdown
## Alert: OutlineQueueDepthHigh

**Meaning:** Worker can't keep up, or workers are dead, or a poison message blocks the queue.
**Dashboards:** [Outline workers] queue depth, oldest job age, worker pod status.
**Runbook:**
1. kubectl -n outline get pods -l app=outline-worker     # are workers alive?
2. Check worker logs for a crashloop / repeated error.
3. If alive but idle and depth climbing → poison message: inspect the dead-letter set.
4. If processing but slow → scale workers: kubectl scale deploy/outline-worker --replicas=4
5. If a bad deploy → helm rollback outline <rev>
**Escalation:** if DB-bound (check pg_stat_activity), see PostgresSlow runbook.
**Postmortem note:** did an alert fire before users noticed? If not → new alert.
```

The test of a runbook: **someone who has never touched the system can follow it under stress.** If it assumes knowledge, it's notes, not a runbook.

### The runbook index you'll accumulate

Seeded from every "failure mode you must deliberately cause" in docs 01–15 — you already *did* each once; now write down what worked:

| Runbook | Source doc |
|---|---|
| Pod Pending / CrashLoop / ImagePull triage | 02 |
| Helm release stuck / rollback | 03 |
| Jenkins build hung / agent not spawning / CD failed mid-deploy | 04 |
| Harbor disk full / GC / pull failures | 05 |
| Postgres failover / connections exhausted / slow queries / PITR | 06, 15 |
| Redis failover / memory full / evictions on queue | 07 |
| MinIO degraded / key revoked | 08 |
| OIDC login failures / JWKS / key rotation window | 09 |
| Outline 5xx / latency / queue depth / poison jobs | 10 |
| Alert storm / Prometheus down / target missing | 11 |
| Loki dropping logs / query timeouts | 12 |
| Node NotReady / DiskPressure / evictions / drain | 13 |
| Suspected compromise / secret rotation | 14 |
| Restore drills | 15 |

---

## The debugging funnel (the skill itself)

Given any symptom, walk **layers bottom-up** (the doc 00 stack), and at each layer ask *the two questions*: what does the evidence say, and what's the cheapest test?

```
1. Is it real?       Check the dashboards against user reports. Reproduce it.
2. When did it start? Correlate with the deploy timeline: helm history, Jenkins builds, terraform applies.
3. What layer?
   node        → describe node, disk/mem/iowait (doc 13)
   k8s         → get events, pod conditions, endpoints (doc 02)
   network     → netcat probes, NetworkPolicy (doc 14)
   dependency  → pg_stat_activity, redis info, minio health (docs 06–08)
   app         → logs with req_id, RED metrics (docs 10–12)
   config/auth → recent configmap/secret changes, cert expiry (docs 03, 09)
4. What changed?     80% of incidents are a change. Find the change first.
```

> **Senior lens — "what changed?" beats "what's wrong?"** Most incidents are regressions, not spontaneous failures. Before deep-diving internals, diff the world against its last-known-good state: `helm history`, `kubectl rollout history`, Jenkins build log, `terraform plan` drift. The fastest debugging session is usually a rollback followed by a diff, not a heroic root-cause hunt under fire. **Stabilize first (rollback/mitigate), root-cause second** — with the evidence preserved (logs/metrics of the failing version).

### The two-question habit

At every layer, before acting: *"What do I expect to see if my hypothesis is right, and what's the cheapest observation that distinguishes it from the alternative?"* This is what prevents the junior loop of restart-everything-and-pray.

---

## Change discipline

The rules that keep day 2 survivable:

- **One change at a time.** Two simultaneous changes means you can't attribute effects — and when both break, you debug a 2-dimensional failure space.
- **Every change is a Git commit or a Helm revision.** If a change can't be found in history, it didn't happen (or it's drift — doc 01 — which is its own incident).
- **Diff before apply.** `terraform plan` (doc 01), `helm diff` (doc 03). No exceptions, including "quick fixes." *Especially* quick fixes.
- **Rollback path stated before you start.** If this deploy goes wrong, what's the undo? If you can't answer before, you won't answer well during.
- **Change windows.** Even solo: pick a time when you can afford 30 minutes of breakage, and when you're fresh. Friday-evening deploys are a meme for a reason.

---

## The routine (the actual day-2 schedule)

**Daily (5 min):**
- Scan Grafana overview + alerts (ack'd? trending?)
- Backup status: last-successful-backup ages (doc 15)

**Weekly (30 min):**
- Review new/changed alerts — anything paging that shouldn't be? (doc 11's noise discipline)
- `helm list -A` + `kubectl get deploy -A` version drift vs. repos
- Disk trends (`predict_linear` panel — doc 13). The concrete query behind that panel:
  ```promql
  # "how many hours until this filesystem fills, at the rate it's been filling?"
  predict_linear(node_filesystem_avail_bytes{mountpoint="/" }[6h], 0)
  / deriv(node_filesystem_avail_bytes{mountpoint="/" }[6h]) * 3600
  # < 48h → investigate/grow; < 4h → page (the "will fill overnight" call, doc 13)
  ```
- Harbor retention/GC ran; scan findings review (doc 05)
- Git hygiene: anything hand-edited in the cluster that isn't in Git? (`terraform plan` empty, `helm diff` clean)

**Monthly (2h):**
- Restore drill: PITR or mirror (doc 15) — timed
- RBAC audit: `kubectl auth can-i --list` sweep (doc 14)
- Dependency updates: base images, chart versions — one component at a time, watch dashboards

**Quarterly (half day):**
- Full cluster rebuild drill (doc 15, scenario 3)
- Secrets rotation batch (doc 14)
- Runbook review: every alert → live runbook entry, still accurate?

---

## Upgrades (the change you can't avoid)

Order matters — upgrade the platform in dependency order, one layer at a time, watching each:

```
1. Nodes/OS         (drain → upgrade → uncordon, one node at a time — doc 13)
2. Kubernetes       (control plane then workers; respect etcd quorum — docs 01–02)
3. Storage operators (CNPG first — everything depends on data — doc 06)
4. Ingress/cert-manager (doc 01)
5. Monitoring/logging (docs 11–12)
6. Jenkins/Harbor    (docs 04–05)
7. App + workers     (docs 03, 10 — normal CD path)
```

> **Threshold — read the release notes for step N before step N-1.** The common upgrade disaster isn't the step you're on; it's the incompatibility two steps ahead (new CNPG needs newer k8s; new chart needs newer CRD). Map the chain first, then execute.
>
> **Failure mode — CRD skew.** Helm charts that bundle CRDs (prometheus-operator, CNPG, Velero) upgrade CRDs *only on install* by default — `helm upgrade` won't touch existing CRDs. You must apply CRD manifests manually before the chart that expects them. Half-upgraded CRDs produce the worst error messages in the Kubernetes ecosystem.
>
> The concrete sequence when upgrading an operator chart:
> ```
> helm get values <old-release> -n <ns> > old-values.yaml       # capture what's live
> helm pull <chart> --untar --version <new>                    # get the new CRDs
> kubectl apply -f ./new-chart/crds/                            # promote CRDs FIRST
> kubectl get crd | grep -E "cnpg|prometheus|velero"           # verify they registered
> helm upgrade <release> <chart> -f old-values.yaml            # now the chart can assume them
> ```
> **The tell that you skipped the CRD step:** the chart's Pods come up and *immediately* crash with `no matches for kind "X" in version "v1"` — that error means the API server doesn't know the CRD yet, which means the CRD never got applied before the controller started. Apply the CRDs, wait for `kubectl get crd` to show them, *then* upgrade the chart. Check every operator chart's docs for its CRD-upgrade procedure — most say exactly this.

---

## Incidents and postmortems

The blameless postmortem, scaled to a homelab (it's for *you*, and it still works):

1. **Timeline** — what happened, when, how detected (alert vs. noticed-vs-users — doc 11's real metric).
2. **Impact** — downtime, data loss vs. RPO/RTO promises (doc 15).
3. **Root cause** — the *systemic* reason, not "I clicked wrong": no alert existed; the runbook lacked the step; the change bypassed the diff discipline.
4. **Action items** — each one a concrete artifact: an alert to add, a runbook section, a policy toggle. **An incident with no action items will recur.**
5. **File it** — `16-operations-runbook/incidents/2026-10-17-queue-stall.md`. The archive becomes your personal casebook — worth more than any certification.

---

## The operating principles (the whole project, distilled)

1. **Everything in Git or derivable from Git.** (docs 01–05, 15)
2. **Diff before apply; rollback before you need it.** (docs 01, 03, 04)
3. **Alert on symptoms, with runbooks, after `for:`-ing out the noise.** (docs 11–13)
4. **Untested backups are hopes.** (doc 15)
5. **Default-deny both network and RBAC; verify by attack.** (doc 14)
6. **One change at a time; find "what changed" first.** (this doc)
7. **Every failure mode should be *deliberately caused once* in peacetime** — the throughline of every doc in this project.

---

## Failure modes you must deliberately cause (final drills)

1. **Full incident simulation**: pick a runbook row, break it at random (roll dice), and recover *only* via the runbook — no freestyle. Where the runbook fails, fix the runbook, not just the system.
2. **Rebuild-the-operator test**: hand the repo + runbooks to a friend (or a fresh Claude session) with cluster access and see if they can deploy a change and restore from backup. Every question they ask is a documentation gap.
3. **The 3am test**: do a deploy and a rollback when tired, following only the runbook. If you can't, the docs aren't done.
4. **Alert-blackout week**: turn off your alerting for a week (in a lab), then audit what you *missed* — calibrates what the alerts are really worth.

---

## Exit criteria for M15 (and the project)

- [ ] Runbook index live; every firing alert maps to an entry
- [ ] The weekly/monthly routine actually executed at least twice
- [ ] One upgrade cycle completed in dependency order without incident
- [ ] One incident fully postmortemed with action items closed
- [ ] Rebuild-from-Git drill under 4 hours (target 1), documented
- [ ] Another human (or agent cold-start) can operate the platform from these docs alone

When all fifteen milestones (M1–M15) check out, re-read doc 00's "How to know you're done" — destroy the cluster, rebuild it, get paged, recover, and explain every tradeoff along the way. **That** is being really comfortable with the entire process. That was the point.
