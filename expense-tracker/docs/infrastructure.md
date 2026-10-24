# Infrastructure — Terraform, k3s, Helm, Edge

> The area you flagged as your main learning curve. This covers the **layering** of
> infrastructure (provision → package → deploy → edge), how Terraform, Helm, and k3s
> divide responsibilities, and the decisions you'll make at each layer. No manifests
> or `.tf` files — the model and the sequence.

---

## 1. The layering (understand this and the rest follows)

Infrastructure has four layers. Each builds on the one below and each has a distinct
tool and job:

```
┌─────────────────────────────────────────────────────────────┐
│  L4  EDGE        Tailscale + NGINX ingress                  │
│                  (access, TLS, load balancing, rate limits)  │
├─────────────────────────────────────────────────────────────┤
│  L3  PACKAGING   Helm charts                                │
│                  (versioned, parameterized app deploys)      │
├─────────────────────────────────────────────────────────────┤
│  L2  ORCHESTRATION  k3s (Kubernetes)                        │
│                  (scheduling, services, PVCs, secrets)       │
├─────────────────────────────────────────────────────────────┤
│  L1  PROVISIONING  Terraform                                │
│                  (the node, the cluster, cloud resources)    │
└─────────────────────────────────────────────────────────────┘
```

**The division of labor — this is the key idea:**
- **Terraform** creates and owns *infrastructure resources*: the machine/node, the
  k3s cluster, networking, DNS, storage classes, and — importantly — it can *install
  Helm releases*. Terraform's job is "make the cluster and its foundational services
  exist, reproducibly."
- **Helm** packages *applications*: your API, consumer, Postgres, Kafka. A chart is a
  parameterized template; values differ per environment.
- **k3s** runs everything: it's the Kubernetes the above two target.
- **Edge** (Tailscale + NGINX) controls who reaches it and how traffic is handled.

**The boundary rule:** Terraform provisions and *bootstraps*; Helm *deploys*; the
cluster *runs*. If you find yourself writing raw Kubernetes YAML that isn't a Helm
chart, ask why — it usually belongs in a chart or a Terraform-managed manifest.

---

## 2. Terraform — what it does here

Terraform is **declarative infrastructure as code**: you describe desired state, it
computes and applies the diff, and it tracks state so it knows what exists.

**Core concepts you must internalize (this is your learning curve):**
- **Providers** — plugins for a platform (the `helm` provider, `kubernetes` provider,
  a cloud provider). Terraform itself is just the engine; providers do the work.
- **Resources** — the things Terraform creates (`helm_release`, `kubernetes_namespace`,
  a VM, a DNS record). Declared as `resource "<type>" "<name>" { ... }`.
- **State** — Terraform's record of what it manages (`terraform.tfstate`). It's how
  Terraform knows the diff. **State is critical and must be backed up** — for a
  learning project, remote state (e.g. an S3/MinIO backend) or at least a committed,
  protected local state file.
- **Plan / Apply** — `terraform plan` shows the diff (what *will* change); `terraform
  apply` executes it. **Always read the plan.** It's your safety review.
- **Variables / outputs** — parameterize per environment; outputs expose values (a
  kubeconfig path, an IP) for later use.
- **Modules** — reusable, composable groupings. Don't over-modularize early; extract a
  module when a pattern repeats (the "rule of three" again).
- **Data sources** — read (not create) existing resources, e.g. look up an existing
  network or image.

**What Terraform owns in this project:**
- The k3s node/cluster provisioning (and, since you've already set it up, Terraform
  may start by *importing* or managing configuration rather than creating from zero).
- Namespaces, storage classes, secrets structure.
- Installing the **Helm releases** for the foundational services (ingress-nginx,
  Postgres, Kafka, observability) via the `helm` provider.
- Network/DNS records for Tailscale access.

**The workflow to build the habit:**
1. Write the `.tf` for one small thing.
2. `terraform plan` — read every line of the diff.
3. `terraform apply` — watch it converge.
4. `terraform destroy` (in a scratch environment) — prove you can tear it down.
5. Commit the `.tf` **and** the state handling strategy.

**Terraform gotchas to know before they bite:**
- **State drift** — someone changes the cluster by hand; next `plan` shows a diff.
  Discipline: change infra only through Terraform, or `terraform import` manual changes.
- **Secrets in state** — Terraform state can contain secrets in plaintext. Protect it
  (remote backend, restricted access). Don't commit secrets.
- **`helm_release` vs `helm` CLI** — Terraform can install charts via the `helm`
  provider (tracked in state) — that's the reproducible path. Ad-hoc `helm install`
  from your shell is not tracked and drifts. Prefer Terraform-managed releases.
- **Providers have versions** — pin them; unpinned providers break on upstream changes.

---

## 3. k3s — the concepts that matter

k3s is a lightweight, single-binary Kubernetes. It's Kubernetes, so the concepts are
the same; it's just packaged for the edge. Learn these:

- **Nodes** — the machine(s) running workloads. You have one.
- **Namespaces** — logical isolation within the cluster. Use them: `app`, `data`,
  `ingress`, `observability`. Cheap separation, cleaner RBAC and quotas.
- **Pods** — the smallest deployable unit (one or more containers sharing network/
  storage). Usually you deploy *controllers*, not bare pods.
- **Deployments** — stateless workloads with replica management and rolling updates.
  Your API, consumer, outbox relay, and the UI are Deployments.
- **StatefulSets** — stateful workloads with stable identity and storage. Postgres and
  Kafka are StatefulSets. This is the correct primitive for databases.
- **Services** — stable network endpoints in front of pods (ClusterIP internally,
  LoadBalancer/NodePort at the edge). How the API finds Postgres, etc.
- **PVCs / PVs** — persistent storage that survives pod restarts. **This is where your
  database data and your archive live.** A PVC is a claim; a PV is the actual storage.
  Understand `StorageClass` and reclaim policy.
- **ConfigMaps / Secrets** — configuration and sensitive config injected into pods.
  Never bake config into images; inject it. Secrets are base64, **not encrypted by
  default** — know that, and consider encryption-at-rest for anything sensitive.
- **Ingress** — routes external HTTP(S) traffic into services, via an ingress
  controller (NGINX here). See §5.
- **CronJobs** — scheduled tasks. Your lifecycle/archival automation
  ([`data-lifecycle.md`](data-lifecycle.md) §4).
- **Probes** — liveness/readiness/startup. Get these right or your rolling updates
  flap.

**The single-node reality (repeat of a warning):** HA for StatefulSets (Postgres
replication, Kafka RF=3) needs multiple nodes. On one node you run *degraded*
topologies that work for learning but lose data on node loss. Learn the production
shapes; run the learning shapes; **document the difference** so you never confuse the
two.

---

## 4. Helm — packaging the deploys

Helm is **templated Kubernetes manifests** with versioning and values.

- **Chart** — a package: templates + `values.yaml` + `Chart.yaml` (metadata/version).
- **values.yaml** — the knobs. Same chart, different values per environment (dev vs
  "prod"). This is how you avoid copy-pasting YAML.
- **Templates** — Go-templated manifests that render from values.
- **Release** — an installed instance of a chart in the cluster, with a revision
  history (rollback = `helm rollback`).

**What you package as charts:**
- Your API, consumer, outbox relay, and UI (you write these charts).
- Postgres and Kafka — **use upstream charts** (e.g. Bitnami) rather than writing your
  own database charts. Learning Helm ≠ writing a Postgres operator. Consume well-made
  charts; write charts for *your* apps.
- The ingress controller and observability agents — upstream charts, installed via
  Terraform's helm provider (§2).

**Helm discipline:**
- **Version your charts** and your app images independently. The chart version and the
  image tag are different things — bump both deliberately.
- **Never hardcode environment values** in templates; put them in `values.yaml` and
  override per environment.
- **Secrets via values, but not committed secrets.** Use sealed secrets, an external
  secret store, or inject at deploy time.
- **`helm lint` and `helm template`** (render without installing) before any install —
  review the rendered YAML.

---

## 5. Edge — Tailscale + NGINX

> **The deep dives live in their own folders now.** This section is the model and the
> decisions; the mechanism, tuning, and hands-on are in:
> [`nginx/`](nginx/) (architecture → reverse proxy → load balancing → rate limiting →
> ingress-in-k3s → caching → security → tuning) and
> [`tls/`](tls/) (how-it-works → certificates/PKI → verification → TLS 1.3 →
> this-project-topology → operational → the hands-on
> [mTLS + cert-generation lab](tls/mtls-and-cert-generation.md)).
> Also: [`rate-limiting.md`](rate-limiting.md) for the algorithms behind the limiter.

Two layers of "who can reach this and how."

### Tailscale (network access)
You've already set this up. Its job: **private access** to the node over an encrypted
mesh VPN, without exposing ports to the public internet. The API is reachable by
devices on your tailnet, not the open internet. This is your access-control boundary
at the network layer.

### NGINX Ingress (traffic management)
The ingress controller is the front door *inside* the cluster. Configure:

- **TLS termination** — HTTPS at the edge (Tailscale gives you a private cert, or you
  manage your own). Terminate TLS at the ingress, plain HTTP to services inside. The
  full decision on which cert strategy fits this topology is in
  [`tls/this-project-topology.md`](tls/this-project-topology.md); the actual generation
  and Go verification are in [`tls/mtls-and-cert-generation.md`](tls/mtls-and-cert-generation.md).
- **Load balancing** — distribute across API replicas. NGINX does this by default;
  tune the algorithm if needed.
- **Rate limiting** — protect against abuse/brute force. This is **per-IP, coarse**
  and complements DRF's per-user throttling ([`drf-jwt-guide.md`](drf-jwt-guide.md)
  §6). Use both: NGINX at the edge, DRF at the app. The algorithms and where each
  layer fits are in [`rate-limiting.md`](rate-limiting.md); NGINX-specific config is
  in [`nginx/rate-limiting.md`](nginx/rate-limiting.md).
- **Routing** — `/api/*` → the API service; `/` → the static UI; `/metrics` →
  observability (restricted).
- **Headers & security** — security headers, request size limits, timeouts.
- **Annotations** — most NGINX behavior is configured via ingress annotations; learn
  the common ones (rate limit, body size, timeouts, TLS).

**The division:** Tailscale decides *who can connect at all*; NGINX decides *what
they can do once connected* (routing, limits, TLS). Neither authenticates users — that's
JWT in the API ([`drf-jwt-guide.md`](drf-jwt-guide.md)).

---

## 6. The deploy sequence (how the layers come up)

Build infrastructure bottom-up, each layer verified before the next:

1. **Node exists** (done) — your k3s node, reachable over Tailscale.
2. **Terraform provisions foundations** — namespaces, storage class, secrets structure,
   and installs the ingress controller via the helm provider. Verify: `kubectl get ns`,
   ingress controller running.
3. **Data layer** — Postgres (StatefulSet + PVC, via upstream chart + Terraform) and
   Kafka + schema registry. Verify: connect, create a DB, produce/consume a message.
4. **App images** — build and push container images for API, consumer, relay, UI. This
   is where [`project-structure-guide.md`](project-structure-guide.md)'s "infra
   references images by tag" rule kicks in.
5. **Helm deploys the apps** — your charts, values per environment. Verify: pods
   healthy, probes passing, rolling update works.
6. **Ingress routes traffic** — `/api` → API, `/` → UI. Verify: reach it over Tailscale,
   get a real JWT, hit a real endpoint.
7. **Observability** — agents + exporters + dashboards
   ([`observability.md`](observability.md)). Verify: metrics flowing, alerts firing.
8. **Lifecycle automation** — the archival CronJob
   ([`data-lifecycle.md`](data-lifecycle.md)). Verify: it runs, archives, alerts.

**The habit:** at each step, `terraform plan` (read it), apply, then *verify in the
cluster* before moving on. Never stack two unverified layers.

---

## 7. Repository layout for infra (guidance, not a tree)

Per [`project-structure-guide.md`](project-structure-guide.md), infra lives as clearly
separated siblings, not inside the app. Decide and document:

- **Terraform** — its own directory, with environments (dev/prod) via separate state
  and variable files, and modules for repeated patterns.
- **Helm** — a chart per deployable (api, consumer, relay, ui), each with its own
  `values.yaml`; shared values per environment.
- **Infra references apps by image tag** — never by source path. Build → tag → deploy.

The decision of "monorepo siblings vs separate repo" is in
[`project-structure-guide.md`](project-structure-guide.md) §4 — start as siblings.

---

## 8. Exercises (Phases 9–11) — your Terraform learning curve

1. **Hello Terraform:** one `helm_release` (the ingress controller). `init`, `plan`
   (read every line), `apply`, verify in-cluster, `destroy`, re-`apply`. *Lesson: the
   plan/apply/state loop.*
2. **State handling:** configure remote state (or a protected local file). Break
   something by hand in the cluster, run `plan`, watch the drift. *Lesson: state and
   drift.*
3. **Namespaces + storage:** create namespaces and a storage class via Terraform.
4. **Deploy Postgres** via an upstream chart through the helm provider. Connect from a
   pod. *Lesson: StatefulSet + PVC + chart consumption.*
5. **Deploy Kafka** the same way; produce/consume across pods. *Lesson: data layer on
   k3s.*
6. **Write your first chart** for the API. Render with `helm template`, lint, install,
   scale replicas, roll back. *Lesson: Helm packaging.*
7. **Ingress + Tailscale:** route `/api` to the API over Tailscale, add TLS and a rate
   limit. *Lesson: the edge.*
8. **Full teardown:** `terraform destroy` in a scratch environment and rebuild from
   scratch. If you can destroy and recreate, you own it. *Lesson: reproducibility.*

Checkpoints in [`checkpoints.md`](checkpoints.md).

---

## 9. Decisions to record in `design.md` / `runbooks.md`

- Terraform state backend and protection strategy.
- Which providers and pinned versions.
- What Terraform owns vs what Helm owns (the boundary, explicitly).
- Namespace layout.
- Upstream charts used (Postgres, Kafka, ingress, observability) and their versions.
- Image registry and tagging scheme.
- Ingress routing, TLS approach, rate-limit values.
- The single-node caveat and what's intentionally degraded.
- The teardown/rebuild procedure (a runbook).
