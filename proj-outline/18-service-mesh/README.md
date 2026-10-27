# 18 — Service Mesh and Service-to-Service Security

**Folder:** `18-service-mesh/`

---

## Teach first: what a service mesh actually is

A **service mesh** is a layer of *infrastructure for networking between services*, deployed as sidecar proxies (or an "ambient" node-level proxy) that sit next to your application pods. It moves cross-cutting network concerns *out of the application code* and into a data-plane proxy:

- **Transport security** — mutual TLS (mTLS) between every service pair.
- **Service identity** — each service is authenticated to every other service by its ServiceAccount / identity.
- **Traffic policy** — retries, timeouts, circuit breaking, rate limiting, canary / weighted routing.
- **Observability** — per-hop metrics, distributed traces, mTLS-logged flows.

> **The one-sentence justification** — your app already talks to Postgres, Redis, MinIO, Keycloak, other Outline pods (server↔worker). Today, *in-cluster* that traffic is **plaintext, unauthenticated, and unpoliced** (doc 14's NetworkPolicy is the coarse version). A mesh makes every hop **authenticated (mTLS), identified (service identity), and policy-controlled (retries/timeouts/circuit-break)** without touching Outline's code.

### Sidecar vs. ambient

| Model | Shape | Tradeoff |
|---|---|---|
| **Sidecar** | One proxy container *per pod* (Istio, Linkerd) | Full per-pod control; but a proxy in every pod = memory + startup cost, and `exec`/`port-forward` get awkward |
| **Ambient / ztunnel** | One proxy per *node*, pod traffic redirected to it (Istio Ambient) | Cheaper, no per-pod footprint; coarser per-pod policy in early versions |

> **Senior lens — sidecar is the default learning choice** because every control lives next to the workload you're debugging. **Ambient is the production-cost choice.** Know both; pick ambient when the sidecar's memory tax hurts on small nodes. For *this* project, sidecar (Istio or Linkerd) is the right first step.

---

## Why this fits *this* project

You've already built service-to-service dependencies (docs 06–10): Outline server→Postgres, server/worker→Redis, workers→MinIO, all→Keycloak for tokens. Right now:

- **No mTLS in-cluster** — doc 14's NetworkPolicy says *who may reach whom*, but it doesn't say *who is this* or *encrypt it.*
- **No retry/circuit-break** — Outline has its own, but Postgres/Redis/MinIO calls have no mesh-level timeout/retry/backoff.
- **No per-service identity** — a compromised pod can still be "whoever" on the wire.

Adding a mesh is the natural **next security layer after NetworkPolicy**: NetworkPolicy = coarse *reachability*, mesh = fine-grained *identity + encryption + traffic control* on top.

> **Tradeoff — when NOT to add a mesh.** A mesh is a *new control plane* with its own failure modes (proxy bugs, version skew, a bad traffic policy that black-holes traffic), its own operators, and per-pod overhead. If your cluster is a handful of services and your traffic is already encrypted at a higher layer (say, the app only talks to a Postgres replica you fully trust in-cluster), **the mesh's cost may exceed its benefit.** The honest L6 answer: *add the mesh when (a) you have service-to-service identity requirements, or (b) you want retries/circuit-break/canaries at the infra layer, or (c) you have a compliance reason to encrypt east-west traffic.* If none of those apply, a mesh is cargo-culting. **For this project you *do* have (a) and (c) — service identity + encrypted east-west traffic is a stated goal — so it earns its place.**

---

## The pieces you'll install

| Component | Role |
|---|---|
| **Istio control plane** (`istiod`) | Config, cert authority, pushes policy to proxies |
| **Envoy** (the data-plane proxy) | The actual sidecar; does mTLS, retries, telemetry |
| **Pilot/CNI** | Redirects pod traffic to the sidecar without `iptables` (Istio) |
| **Citadel / cert manager** | Issues short-lived mTLS certs to service identities |

(Or, with Linkerd: `linkerd-control-plane` + per-pod `linkerd-proxy`. Simpler, fewer knobs — **often the better teaching choice**.)

> **Tradeoff — Istio vs. Linkerd.** Istio: most powerful (Wasm filters, full traffic-splitting, service-to-service authz), heaviest, more to learn and to break. Linkerd: minimal footprint, fewer features, easier to run on a homelab. **For *learning the mesh concepts* — mTLS, identity, retries, telemetry — Linkerd is cleaner; for *learning the full surface* an L6 is expected to know, Istio.** Pick Linkerd to get to "the mesh works" fast, then read Istio's docs for the knobs Linkerd doesn't expose.

---

## mTLS and service identity — the thing that matters most

Every pod that's part of the mesh gets a **workload identity** (from its ServiceAccount) and a short-lived **certificate**. Two pods that talk, both have proxies, and the proxies do **mTLS**: each verifies the other's cert, learns the other's *identity*, and only then forwards traffic.

```
Outline-server pod → [its Envoy]  ←mTLS: I am "outline-server" →  [Postgres Envoy] ← "I am postgres"
```

Consequences a senior reasons about:

- **AuthZ policies become identity-aware.** "Outline may talk to Postgres on 5432" is now `FROM service outline-server TO service postgres PORT 5432` — *enforced by identity*, not just IP (doc 14). This is strictly better than NetworkPolicy: a pod that *spoofs an IP* can't spoof its identity.
- **Certs are short-lived.** If a cert leaks, it expires in minutes-to-hours. This is how a mesh is *safe to rotate.*
- **The data plane is now in the path of every hop.** A broken Envoy config = your app can't reach its DB. **The mesh is a new SPOF to protect** (the control plane; the proxies themselves fail open to direct connection by design in most meshes, but *verify that's actually your config*).

> **Failure mode — the mesh black-holes your traffic.** You enable mTLS + an authorization policy, and suddenly Postgres connections *from Outline* are denied because the policy said "outline-server" but the caller is actually "outline" (name drift). The error looks like a Postgres outage but is a *policy* error. **When you add a mesh, re-test every dependency call.** Your doc-06/10 "deliberately cause failures" drills must now include "add the mesh, watch what breaks."

---

## Traffic policy: retries, timeouts, circuit breaking

The infra-layer version of what Outline's code does in-app. The mesh gives you *defaults* that protect shared dependencies:

- **Timeout** — bound every call. (Outline→Postgres with no timeout = one slow query wedges a thread forever.)
- **Retries** — retry on *connection* errors, not 5xx (retries of non-idempotent writes are dangerous — doc 21).
- **Circuit breaker** — if Postgres errors N times in M seconds, stop sending for a bit and let it recover (prevent a thundering herd).
- **Rate limit / concurrency** — cap how many in-flight requests a pod can hold to the dependency.

> **Threshold — retries × timeout = your worst-case latency.** A call with timeout 2s and 3 retries = up to ~8s before giving up. Multiply by the number of retries your *caller* also does and you've got latency that compounds. **Set the mesh timeout tighter than the app's own timeout; don't stack them.** This is a detail juniors miss and L6s catch in review.

> **Tradeoff — idempotency before retries.** Retrying a `POST /create` can double-create. Retrying a `GET` is safe. The mesh's retry policy must be scoped to *idempotent* calls only, or you move the retry to the app where it can add an idempotency key. **Retries are an idempotency problem first, a network problem second** (doc 21 develops this).

---

## Observability: traces and flow logs

The mesh makes **distributed tracing** realistic — every hop through a proxy is a span. That finally lets you answer "this request was slow — *which* hop was slow?" (the trace question raised in doc 11). Pair the mesh with:

- **Envoy metrics** — per-hop request/latency/error, by service identity.
- **Distributed trace** — one trace across Outline-server → Postgres, Outline-worker → MinIO.
- **Access / flow logs** — *who called whom* on mTLS, which is your service-to-service audit trail (and feeds doc 14's security monitoring).

> **Senior lens — the mesh's telemetry is where you *find* the wrong policy.** A "Postgres is slow" alert is a symptom; the mesh trace tells you it's the *retry storm* from an aggressive retry policy. Without the mesh's per-hop view you'd tune Postgres for hours and never find the real cause.

---

## The workflow you'll live in

```
# Mesh is config-as-code; inspect it
istioctl proxy-config routes outline-server-0 -n outline   # what routing does this sidecar have
istioctl authn tls-check outline-server-0                    # is mTLS actually on?
kubectl get gateways, virtualservices, destinationrules -n outline

# Traffic policy
kubectl get pod outline-server-0 -o jsonpath='{..image}'     # confirm envoy sidecar present
istioctl x -f virtualservice-yaml                            # simulate: what does this VS route to?
```

> **`istioctl x` (xdebug / simulation) is the L6 tool** — it tells you, *without changing anything*, "if I applied this policy, where would this request go?" It's the mesh version of `helm diff` / `terraform plan` from docs 03/01.

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| Mesh vs. no mesh | Add when you need service identity / mTLS / east-west encryption / infra-level retries — not as cargo |
| Istio vs. Linkerd | Linkerd to learn fast; Istio for the full knob set; ambient when sidecar cost hurts |
| Data plane | Sidecar (learning) → Ambient (cost) |
| mTLS | Peer-to-peer; certs short-lived; the SPOF to protect |
| Timeouts/retries | Mesh timeout *tighter* than app's; retries only on idempotent calls; cap in-flight |
| Authz | Identity-aware (from doc 14 NetworkPolicy → mesh AuthorizationPolicy) |
| New SPOF | Control plane + proxies; fail-open design, tested |

---

## Failure modes you must deliberately cause

1. **Add mTLS + an AuthorizationPolicy** → watch a dependency call get *denied* by a policy that looks like a DB outage. This is *the* mesh failure mode; rehearse the diagnosis.
2. **Set an aggressive retry policy** on a non-idempotent call → observe duplicate writes; learn why retries are an idempotency problem.
3. **Stack timeouts** (mesh 5s + app 10s) → measure worst-case latency; fix the layering.
4. **Take the control plane down** → verify proxies fail *open* (traffic still flows) or *closed* (nothing flows) — know which you have.
5. **Trace a slow request across hops** → confirm the mesh trace tells you the slow hop; this is the payoff for the overhead.
6. **Rotate the mesh certs** → verify short-lived cert renewal works and nothing hard-pins an old cert.

---

## The L5/L6 lens: what this signals

| Probe | L6 answer |
|---|---|
| "Why a mesh at all?" | "Service-to-service identity + mTLS east-west encryption + infra-level retries/circuit-break that we *don't* want in Outline's code. I added it for those three; I'd not add it if we had no identity or encryption requirement." |
| "Istio or Linkerd?" | "Linkerd to reach 'the mesh works' cheaply and learn the concepts; I've read Istio for the full traffic-splitting / Wasm surface. Ambient is the cost path when sidecar memory bites on small nodes." |
| "What's the new failure mode?" | "The mesh is a new SPOF — control plane + proxies in the data path. I verify fail-open behavior, and I re-test *every* dependency call after adding the mesh, because a bad AuthorizationPolicy looks exactly like a DB outage." |
| "How does it interact with NetworkPolicy?" | "NetworkPolicy is coarse reachability (who reaches whom by IP); the mesh is fine-grained identity (who *is* the caller) + encryption + traffic policy. I run *both*: policy denies the flow, mesh denies the unauthenticated identity." |

---

## Exit criteria

- [ ] A mesh (Istio *or* Linkerd) installed and injecting into the `outline`, `database`, `cache`, `storage` namespaces
- [ ] mTLS peer-to-peer verified (`istioctl authn tls-check` / linkerd check)
- [ ] A service-to-service AuthorizationPolicy enforced *by identity*, layered over doc 14's NetworkPolicy
- [ ] A retry/timeout/circuit-break default set *tighter* than the app's; worst-case latency measured
- [ ] A distributed trace captured across server→Postgres
- [ ] The black-hole failure (bad policy = outage symptom) diagnosed at least once deliberately
- [ ] You can state, without notes, why the mesh *earns its place* here and when you would *not* add it

Next: `19-gitops` — how the cluster converges to Git instead of Jenkins pushing it.
