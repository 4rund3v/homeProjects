# 22 — Testing Strategy: The Layered L6 Model

**Folder:** `22-testing/`

---

## Teach first: testing is *economics*, not *coverage*

Junior testing is **coverage** ("how many lines did I hit?"). L6 testing is **risk allocation** ("where's a bug *costly* to find late, and how do I catch it *cheap, early*?"). The test suite you write should mirror the *cost of a bug escaping*, not the size of the codebase.

> **The L6 reframe — tests are a *decision*, made in layers.** Each layer catches a different class of bug at a different cost/speed. The senior question is not "what do we test" — it's **"which layer catches *this* failure, and is it the *cheapest* layer that can?"** Testing everything with the slowest test you'd use for one of them is the classic cost failure.

---

## The layered model (and what each layer is *for*)

| Layer | What it's *for* | Speed | Outline example |
|---|---|---|---|
| **Unit** | A function's *logic* in isolation | ms | a pure `validate(doc)`; a price-per-doc rule |
| **Integration** | Components *together* against a real dep | s | "Outline + real Postgres + real Redis" writes a doc, reads it back |
| **Contract** | Two *sides* of an interface agree | s | the client's request schema == the server's expectation (doc 21) |
| **End-to-end (E2E)** | The *user's* journey through the real system | min | "login → create doc → share → log out" |
| **Load / performance** | The *system under pressure* | min | "can the server + Postgres hold 1k RPS without p99 blowing?" |
| **Chaos / failure** | The *failure modes* | min | "kill the primary Postgres; does a standby promote?" (doc 06) |
| **Security** | The *attack surface* | — | "does this endpoint auth correctly? (doc 14)" |

> **The ordering is *a funnel*, not a hierarchy.** Unit tests are the wide top (many, fast, catch dumb bugs cheaply). E2E/chaos are the narrow bottom (few, slow, catch the expensive "did we wire it all together" bugs). **Most bugs should *never* reach the slow bottom layers — the cheap top layers filter them.** A system where you only catch things in E2E is one where your unit tests are weak.

### The shape of a *healthy* test pyramid

```
              /\        E2E:       few, high-value user journeys
             /  \       Contract:  each service boundary
            /    \      Integrat.:  each real dependency pair
           /      \     Unit:       many, the bulk of tests
          /________\
```

A *broken* shape is the **ice-cream cone** (few units, lots of E2E) or the **hourglass** (lots of E2E, none mid-layer). The cone means the slow layers are doing work the fast layers should have caught — the whole suite is *slow and flaky.* **Diagnose the shape, not just the count.**

---

## The tests this project *specifically* needs

Map each layer to a concrete Outline risk (this is the part that makes it not-generic):

| Layer | The risk it's *for* | The drill |
|---|---|---|
| **Unit** | Logic bugs in the app (validation, permissions, rendering) | pure functions + a real Postgres-backed model test |
| **Integration** | *Outline↔Postgres↔Redis* wiring; migrations | CI spins up real Postgres+Redis, runs the app, asserts a write/round-trip |
| **Contract** | doc 21's API: a client/servers that *disagree on the shape* | `buf breaking` / OpenAPI diff in CI — the contract *is* the test |
| **E2E** | "the whole login→create→share flow works" | a CI job that drives the real deployed cluster (doc 04's post-deploy smoke, extended) |
| **Load** | "does the server scale? does Postgres hold RPS?" (doc 10's HPA) | a load test with a p99 target; confirm HPA fires |
| **Chaos** | *the resilience of the stack* — Postgres failover, node loss, mesh black-hole (docs 06, 13, 18) | the drills *are* the tests: "kill the primary, does it promote within SLO?" |
| **Security** | doc 14: RBAC, network policy, secret handling, the *mesh* mTLS | "a pod can't reach Postgres from the wrong namespace; a secret is rotated without outage" |

> **The L6 insight — chaos tests *are* the failure-mode drills from docs 01–15, formalized into CI.** Every "deliberately cause this failure" you've done by hand in this project is a *chaos test* you can put in a pipeline and re-run on every deploy. **The project's earlier docs *are* your chaos suite; this doc is where you make them *repeatable and gated*.**

---

## The two disciplines that separate L6 from the rest

### 1. Contract testing (doc 21 made concrete)

Two services built by two people, two languages, two teams: the *only* thing that should be in sync is the **contract** (the schema). **Contract testing** asserts that "the client's expected request/response shape == the server's actual shape" *without deploying either.* In CI:

```
client side:  "my request sends {workspace_id, idempotency_key, title}"
server side:  "I expect {workspace_id, idempotency_key, title}"
contract:     buf breaking / OpenAPI diff passes only if the two agree
```

> **The L6 detail — provider-side contract tests.** The *server* (provider) publishes a *consumer-driven* contract: "here's every shape my consumers actually use." A server change that *breaks* one of those is caught *by the consumer's test*, not by a lucky full-suite run. This is how you change a service without breaking the 50 teams that use it. **It's the mechanism that makes *large* multi-service systems evolvable.**

> **Failure mode — the *over*-strict contract gate.** A `buf breaking` / consumer-driven check that's *too* strict (flags additive changes that are actually safe, or a too-narrow "exactly these fields" assertion) produces the same trust-erosion as a flaky test: **people start ignoring it.** The L6 discipline *from the flakiness section applies to the contract layer too* — quarantine a contract-gate false-positive instead of deleting the check. **A contract gate that fires on every additive change is no different from a flaky test that fires on every PR; it gets muted, and then it catches the real break too.**

### 2. Canary *analysis* (doc 19 made concrete)

Progressive delivery (doc 19) advances a canary **only on a metric signal.** The test that earns it: **inject a bad signal on the canary variant and confirm the analysis holds it at 5% and rolls back.** Without *that* test, your canary is "a slow rolling update" — it ships 100% and *then* the alert fires. **The canary is only as good as the analysis that gates it; test the analysis, not just the rollout.**

---

## Flakiness: the test that's *actually* the problem

Flaky tests (pass/fail at random) are **the #1 L6 test-system threat.** A flaky test that fails intermittently gets *ignored* — and the day it fails for a *real* reason, it's treated as flaky. **Flakiness is not a test-quality issue; it's a *trust* issue. A suite you don't trust is a suite you've silently stopped running.**

> **The L6 discipline — quarantine, don't delete.** A flaky test goes into a `flaky` suite (still runs, but its failure doesn't block the PR). It's *triaged* (fixed or proven-stably-broken) on a deadline. **Deleting the flaky test deletes the signal.** Quarantine keeps the signal and protects the trunk.

**Why tests go flaky in *this* project specifically:**
- A test that shares state with a real Postgres/Redis (doc 06/07) that *another* test just mutated → **use a fresh, reset DB per test** (or transactional rollbacks).
- A test that depends on timing (a job "should be processed within 1s") → **make it eventual** (poll with a deadline, don't sleep-and-assert).
- A test that hits the mesh (doc 18) and depends on a policy that's *asynchronous* to apply → **wait for the policy to be active before asserting.**

---

## The CI test gates (what blocks a merge)

```
PR → lint → unit (fast, gate on <60s) → contract (buf breaking / OpenAPI diff)
   → integration (real Postgres+Redis, gate on <5min)
   → E2E (real cluster, the user journey)
   → load / chaos (canary analysis + a resilience drill)
   → security (RBAC/netpol/secret checks)
```

> **Threshold — the *fast* gate matters more than the *complete* gate.** A 12-minute suite gets skipped under pressure; a 60-second gate is *always* run. **Front-load the cheap, high-signal tests (unit + contract) into the fast gate that blocks a merge *before* the slow layers.** The slow layers (E2E/chaos/load) run on *every* commit that passed the fast gate — so the fast gate's job is to make the slow gate *run at all.* This is why "test in layers" is an *architecture* decision, not a "run more tests" one.

> **Why *60s* specifically (the number a panel will ask you to justify):** it's a *behavioral* threshold, not a magic one. The rule of thumb: **if a gate takes longer than a person's patience window while *waiting for the merge to unlock*, people stop waiting for it and start bypassing it** — and a bypassed gate catches nothing. 60s is short enough that a developer stays in the flow; past ~2–3 min, bypasses and "I'll let it run in the background" start happening at non-zero rates. So the split is: **fast gate = everything that can run in <60s** (unit + contract, parallelized); **everything slower is the *slow* gate that runs *because* the fast gate passed.** If your unit suite is 4 minutes, that's a signal it needs *sharding* (split into N parallel buckets, each <60s) — the fix is concurrency, not patience. **The panel question "why 60s" is answered by "because that's where *people stop waiting*, and a gate nobody waits for is a gate that never runs."**

---

## The workflow you'll live in

```
# The funnels
npm run test:unit                          # the 60s gate
buf breaking                                # the contract gate (doc 21)
npm run test:integration -- --db reset     # the real-dep gate
kubectl port-forward svc/outline 3000:3000  # then drive the E2E journey
k6 run load-test.js -e p99=500ms          # the load gate (the HPA target, doc 10)

# The chaos gates (the failure drills made CI)
make chaos-failover-postgres               # doc 06, now automated
make chaos-kill-node                       # doc 13
make chaos-disable-mesh-policy             # doc 18 — the black-hole drill
```

**What the load gate *asserts* (the `p99=500ms` isn't a print, it's a pass/fail):** k6's `-e p99=500ms` is an **exit criterion** — the job *fails the build* if p99 exceeds 500ms over the test. A minimal shape:

```js
// load-test.js — enough to assert the HPA target, doc 10
import http from 'k6/http';
import { check } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 50 },   // ramp to 50 VUs
    { duration: '1m',  target: 50 },    // hold (let the HPA have a chance to scale)
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    p99: ['p99<500'],      // exit-criterion: fail build if p99 ≥ 500ms
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  const r = http.get('http://outline:3000/api/health');
  check(r, { 'status 200': (r) => r.status === 200 });
}
```

And the HPA it's gating on (doc 10) — the test and the scaler must agree on the number:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: { name: outline-server, namespace: outline }
spec:
  scaleTargetRef: { apiVersion: apps/v1, kind: Deployment, name: outline-server }
  minReplicas: 2
  maxReplicas: 6
  metrics:
  - type: Resource
    resource:
      name: cpu
      target: { type: Utilization, averageUtilization: 75 }
  behavior:
    scaleDown: { stabilizationWindowSeconds: 300 }   # don't flap
```

> **The gate-to-metric link a panel will check:** the load test holds 50 VUs for a full minute so the HPA's 75% CPU target actually triggers a scale-out, and the test only passes if p99 stays under 500ms *while* that happens. **If you test the load but never assert the HPA fired, you've measured a 2-replica ceiling, not the scaler.** Assert both.

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| Test shape | Pyramid; diagnose the *shape* (cone/hourglass = broken), not just the count |
| What catches what | Cheap layers catch cheap bugs early; *never* let a slow layer be the first line of a class of bug |
| Contract | Consumer-driven; a server change that breaks a consumer's shape is caught by the *consumer's* test |
| Canary | The analysis gate *is* the test; inject a bad signal and confirm it holds at 5% |
| Flakiness | **Quarantine, never delete;** flaky = trust problem, not a test bug |
| CI speed | Fast gate (<60s) blocks merges; slow layers run *because* the fast gate passed |
| What's *this* project's | The doc 01–15 "cause a failure" drills, formalized into CI gates |

---

## Failure modes you must deliberately cause

1. **Make a test flaky on purpose** (shared Postgres state) → watch it get *ignored*; then quarantine it and *fix* it. Feel why trust is the whole thing.
2. **Let the suite bloat past the 60s gate** → watch people start skipping it; front-load the fast gate.
3. **Ship a canary with *no* analysis gate** → it ships 100% and the alert fires *after*; add the analysis step and inject a bad signal; watch it hold.
4. **Change a service's contract silently** (break the shape) → the consumer's contract test catches it *before* deploy; feel why the contract is the test.
5. **Skip the chaos drill** (never kill Postgres in CI) → the day real failover is needed, it's *unproven*; make it a gate.
6. **A timing-dependent test** (job "done in 1s") → make it eventual (poll to a deadline); feel why `sleep`-and-assert is the flaky-test factory.
7. **A timing-based *chaos* gate without a deadline** ("failover within SLO") → the same flaky factory, in the chaos layer: "within SLO" needs a *concrete* wall-clock cap (e.g., "promote within 90s"), otherwise the gate is a sleep-and-assert flake just like #6. **The doc warns about this for unit tests; apply the identical discipline to chaos gates — "failover succeeded" must mean "promoted *by time T*", not "eventually."**

---

## The L5/L6 lens: what panels probe to *refute* you

Not "what I'd say" — **what a hostile panel will ask to expose that you're reciting**, and the concrete number / artifact that *stops* the refute.

| Panel probe | The refute they're looking for | The concrete artifact that *stops* it |
|---|---|---|
| "How many tests?" | "You optimize coverage, not risk." | "I optimize *layer*: many fast units, few high-value E2E. I'd diagnose the *shape* — a cone/hourglass is the real bug. Here's my suite's layer split." |
| "What's the most expensive test?" | "You don't know *why* it's cheap." | "E2E/chaos — and only because the cheap layers should have caught what they catch. If a bug first surfaces in E2E, my unit layer is too weak. I've traced one such bug up from E2E to the unit that should have caught it." |
| "Why 60s for the fast gate?" | "You picked a number." | "It's *where people stop waiting for the merge* — past ~2-3 min, bypasses start. The fix for a slow unit suite is *sharding into <60s buckets*, not patience." |
| "How do you keep a big system evolvable?" | "You run the gate, not the model." | "Consumer-driven contract tests: a server change that breaks a consumer's *shape* is caught by the *consumer's* test. And I know the failure of a *too*-strict gate — it gets muted exactly like a flaky test; I quarantine false-positives instead of deleting the check." |
| "What's the *real* test-system threat?" | "Flakiness." | "Trust. A flaky test you've stopped trusting is a test you've stopped running. I quarantine (not delete), front-load a <60s gate so the slow layers *actually get run*, and I apply the same eventual/poll discipline to *chaos* gates ('promoted by 90s', not 'eventually')." |
| "How do you split fast/slow gates concretely?" | "You can't name the split." | "Fast (<60s, blocks the PR): unit + contract, sharded. Slow (runs *because* the fast gate passed): integration on real deps, E2E, load, chaos. The split is *latency of the layer*, not a preference." |

> **The meta-skill, applied to testing:** bring the *shape* diagnosis, the *60s* justification, and the *flakiness-as-trust* framing as artifacts, not slogans. The panel can ask "derive the split for *our* suite" — the one who's only reciting generalities fails that.

---

## Exit criteria

- [ ] You can state the *shape* (pyramid) and diagnose a cone/hourglass
- [ ] A contract gate (`buf breaking` / OpenAPI diff) blocks a merge on a *shape* change (doc 21)
- [ ] Integration tests against real Postgres/Redis with *clean* state (the shared-state flake closed)
- [ ] A canary with a *tested* analysis gate that holds on a bad injected signal (doc 19)
- [ ] A flaky test quarantined (not deleted), with the triage deadline
- [ ] The doc-01–15 failure drills expressed as CI chaos gates
- [ ] A *fast* gate (<60s) that the slow layers run *because* it passed

Next: `23-leadership-impact` — where all of this becomes the L6 *career* material.
