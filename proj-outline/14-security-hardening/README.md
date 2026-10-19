# 14 — Security Hardening: RBAC, NetworkPolicies, and Secrets

**Folder:** `14-security-hardening/`
**Milestone:** M13 — Security

---

## Teach first: the attacker's view of your cluster

Security work is unintuitive until you adopt the attacker's perspective. Your cluster, as built through doc 10, looks like this to an attacker:

```
Internet ──▶ ingress (443) ──▶ outline pods
                                    │
                    ┌───────────────┼──────────────┐
                    ▼               ▼              ▼
               Postgres         Redis           MinIO
                    ▲               ▲              ▲
                    └──── any pod in the cluster can reach all of these ────┘
```

**The k8s network is flat by default** (doc 02). If someone gets code execution inside *any* pod — a dependency vulnerability in Outline, a malicious npm package in a build — they can:

1. Read the pod's env vars → **steal the database URL, Redis password, S3 keys** (all injected as env).
2. Reach Postgres/Redis/MinIO directly using those creds.
3. Query the k8s API with the pod's ServiceAccount token → if that SA is over-privileged (default often is), **read every Secret in the namespace or cluster**.
4. From Jenkins' SA (doc 04), potentially **deploy arbitrary workloads** — game over.

Hardening = cutting each of those paths. The controls map one-to-one:

| Attacker step | Control |
|---|---|
| Reach dependencies from a compromised pod | **NetworkPolicy** |
| Read secrets via env vars | (partly unavoidable — but bound each secret's *scope*) |
| Use the pod's SA against the API | **RBAC + automountServiceAccountToken: false** |
| Run as root / escape to the node | **PodSecurity Standards, runAsNonRoot** |
| Get secrets from Git or CI logs | **External Secrets / Sealed Secrets** |
| Pull a poisoned image | **admission policy, signed images** |

---

## RBAC: who can do what to the API

Three objects, one model:

- **Role** — a set of permissions (`apiGroups, resources, verbs`) **within a namespace**. **ClusterRole** — cluster-wide (or namespace-scoped when bound via RoleBinding).
- **RoleBinding** — grants a Role to a **subject** (user, group, or ServiceAccount) in a namespace. **ClusterRoleBinding** — cluster-wide.

```yaml
kind: Role
metadata:
  namespace: cicd
  name: deployer
rules:
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "watch", "patch"]     # no create/delete — deliberate
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["get", "list", "watch"]
---
kind: RoleBinding
metadata:
  namespace: cicd
  name: jenkins-deployer
subjects:
- kind: ServiceAccount
  name: jenkins
  namespace: cicd
roleRef:
  kind: Role
  name: deployer
```

### The two RBAC deployments you'll actually build

**1. Jenkins' deploy SA** (referenced since doc 04). Principle: **Jenkins should be able to deploy Outline and nothing else.** Not read Secrets in other namespaces, not create pods arbitrarily, not touch nodes.

But note: if CD runs `helm upgrade`, Helm needs broad powers in the *target namespace* (read/write Deployments, Services, ConfigMaps, Secrets — Helm stores release state in Secrets). Scope it:

```yaml
# Role for helm in the outline namespace
rules:
- apiGroups: ["", "apps", "networking.k8s.io", "autoscaling"]
  resources: ["*"]
  verbs: ["*"]        # within the namespace only — the boundary that matters
```

Namespaced `*` is a reasonable middle: **the namespace is the security boundary, not the verb list.** A Jenkins SA that is cluster-admin is the failure mode; a Jenkins SA that is god-of-one-namespace is workable.

**2. Outline's app SA.** Outline's pods need **zero** Kubernetes API access. So:

```yaml
spec:
  template:
    spec:
      serviceAccountName: outline
      automountServiceAccountToken: false   # don't even mount the token
```

> **Senior lens — `automountServiceAccountToken: false` is the most underused hardening flag in Kubernetes.** Every pod gets an API token mounted at `/var/run/secrets/kubernetes.io/serviceaccount/token` by default. For the vast majority of workloads — including Outline — it's pure attack surface: a stolen token + an over-permissive Role = lateral movement. Turn it off everywhere the app doesn't call the k8s API (which is: almost everywhere). Only Prometheus operators, controllers, and CNPG-style operators need tokens.

### RBAC auditing

```
kubectl auth can-i --list --as=system:serviceaccount:cicd:jenkins -n outline
kubectl auth can-i create pods --as=system:serviceaccount:cicd:jenkins -n outline
kubectl auth can-i read secrets -n kube-system --as=system:serviceaccount:outline:outline   # should be "no"
```

> **Threshold — audit quarterly and after every chart install.** Charts create their own SAs and bindings; over months, permissions accrete. `kubectl auth can-i --list` per SA is the poor man's access review. Ask of every line: "if this credential leaked, what's the worst day?"

---

## NetworkPolicies: segmenting the flat network

Default behavior: **everything can talk to everything.** NetworkPolicy flips selected pods to **default-deny, allow-listed**:

```yaml
# 1. Deny all ingress to Postgres
kind: NetworkPolicy
metadata:
  name: pg-default-deny
  namespace: database
spec:
  podSelector: {}          # all pods in namespace
  policyTypes: [Ingress]
---
# 2. Allow only Outline to reach Postgres 5432
kind: NetworkPolicy
metadata:
  name: pg-from-outline
  namespace: database
spec:
  podSelector:
    matchLabels: { cnpg.io/cluster: outline }
  ingress:
  - from:
    - namespaceSelector:
        matchLabels: { kubernetes.io/metadata.name: outline }
      podSelector:
        matchLabels: { app: outline }
    ports: [{ protocol: TCP, port: 5432 }]
```

The target matrix you'll enforce:

| Dependency | Allowed from | Port |
|---|---|---|
| Postgres | outline namespace (server+worker), CNPG operator, backup jobs | 5432 |
| Redis | outline namespace | 6379 |
| MinIO | outline, pg-backup jobs, Loki, Harbor(?) | 9000 |
| Keycloak | outline (redirects are user-side), ingress | 8080/8443 |
| Jenkins controller | Jenkins agents only | 50000 + web via ingress |
| kube-api | nobody from app namespaces | 6443 |

> **Failure mode — the silent breakage.** NetworkPolicies fail *closed* and *silently*: a too-strict policy looks exactly like a network outage of the app. When "the app suddenly can't reach the DB" after a policy change, the policy is the first suspect, not the fifth. Debug with a temporary netcat pod in each namespace:
> ```
> kubectl run tmp --rm -it --image=busybox -n outline -- nc -zv postgres.database.svc.cluster.local 5432
> ```
> Also: **policies require a CNI that enforces them.** Flannel (k3s default, doc 01) *ignores* NetworkPolicies — they validate, apply, and do nothing. You need Calico or Cilium. If you've been writing policies on Flannel, you've been writing documentation, not security. **Verify enforcement by testing that a blocked connection actually fails.**

> **Senior lens — default-deny per namespace is the goal state.** For each namespace: one `podSelector: {}` deny-all, then explicit allows. Start with the stateful namespaces (database, cache, storage) — highest value, lowest blast radius — then identity, then the apps. Do it incrementally *after* observability (doc 11) is up, so you can see what you broke.

---

## PodSecurity Standards: what pods may *be*

RBAC controls who talks to the API; NetworkPolicy controls who talks to whom; **PodSecurity controls what a pod is allowed to be** — root? privileged? host mounts?

```yaml
# namespace-level enforcement
apiVersion: v1
kind: Namespace
metadata:
  name: outline
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/audit: restricted
```

Three levels: `privileged` (anything) → `baseline` (blocks the worst: hostNetwork, hostPID, privileged containers) → `restricted` (must runAsNonRoot, drop ALL capabilities, seccompProfile, no root FS write).

> **Tradeoff — enforce vs. warn.** Flipping a namespace to `enforce: restricted` rejects non-compliant pods at admission — including your own, mid-deploy, at 3am. **The senior sequence: `warn` first (you see violations in `kubectl` output, nothing breaks), fix your charts, then `audit` (violations logged as events), then `enforce`.** Your own Outline chart must set `runAsNonRoot: true`, `readOnlyRootFilesystem: true` (plus an `emptyDir` for /tmp), `allowPrivilegeEscalation: false`, `capabilities: drop: [ALL]`. The kube-prometheus-stack and CNPG charts already comply — mostly; expect to patch a DaemonSet or two.

**Related admission controls worth knowing (implement later):** image verification (only images signed/scan-passed from Harbor pull — Kyverno or Sigstore policy-controller), and registry restriction (nothing pulls from docker.io directly, only via the Harbor proxy — doc 05).

---

## Secrets management: the full lifecycle

By now you have secrets in several places: k8s Secrets (rendered by Helm, doc 03), Jenkins credentials (doc 04), Harbor robot accounts, MinIO keys, Keycloak client secrets, Terraform state (doc 01). The mature move is **one source of truth**:

**External Secrets Operator (ESO)** — syncs from a backend (Vault, or even a MinIO-encrypted store) into native k8s Secrets:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: outline-secrets
  namespace: outline
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: lab-backend
    kind: ClusterSecretStore
  target:
    name: outline-secrets        # the native Secret your pods mount (Pattern B, doc 03)
  data:
  - secretKey: database_url
    remoteRef: { key: outline/database_url }
```

**Sealed Secrets** — the alternative for GitOps-style flows: encrypt with the cluster's public key, commit the encrypted blob, only the in-cluster controller can decrypt. Simpler than ESO+Vault; rotation is its weakness (re-encrypt on rotate).

> **Tradeoff — Sealed Secrets vs. ESO.** Sealed Secrets: secrets live encrypted *in Git* (great for pure GitOps, one controller, no backend to run); rotating means re-sealing every affected secret by hand. ESO: secrets live in a real backend with real rotation, richer (AWS/GCP/Vault backends) — but you now operate that backend. **For this project: start Sealed Secrets (simpler, Git-native), graduate to ESO+Vault when you want rotation drills.** Either beats the common baseline: plaintext in values.yaml.

### The k8s Secret baseline (regardless of tool)

1. **Enable etcd encryption at rest** — otherwise every Secret is base64 in etcd; anyone with etcd access or an etcd backup reads everything.
2. **RBAC-restrict Secret reads** (`get/list/watch secrets` is a privileged verb — treat it like root).
3. **Never log secrets** — including Helm values (`helm get values` prints what you passed; docs 03–04).
4. **Rotate on a schedule** — the drill: rotate the DB password end-to-end (Secret → PgBouncer → pods restart → app reconnects) without an outage. If you can't, you've found a hard-coding somewhere.

---

## Supply chain: the image path

You already have the pieces (docs 04–05); assemble them into policy:

- CI builds from a *pinned* base image (digest, not tag) pulled via Harbor's proxy cache.
- Trivy scans at push; CRITICAL blocks (doc 05).
- (Later) sign images with cosign in CI; admission (Kyverno) verifies signature in-cluster.

> **Senior lens — threat-model honestly.** For a homelab, cosign+Kyverno is a capstone exercise, not a day-one need. The order of actual payoff: (1) `automountServiceAccountToken: false` + tight RBAC, (2) NetworkPolicy with an enforcing CNI, (3) no secrets in Git, (4) non-root pods, (5) scanned images, (6) signed images. Each step is 10× more valuable than the one after it. Do them in order and stop when the marginal value dies.

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| App SAs | No API access; `automountServiceAccountToken: false` |
| Jenkins SA | Namespace-scoped; never cluster-admin |
| NetworkPolicy | Requires Calico/Cilium; default-deny per namespace; verify by test |
| PSS | warn → audit → enforce sequence; restricted for app namespaces |
| Secrets | Sealed Secrets to start; ESO+Vault for rotation; etcd encryption on |
| Image path | Pinned bases, scanned, (later) signed + admission-verified |
| Audit cadence | `kubectl auth can-i --list` quarterly + after chart installs |

---

## Failure modes you must deliberately cause

1. **Attack yourself from a pod**: `kubectl exec` into Outline, `cat /var/run/secrets/.../token`, try `kubectl get secrets` with it. (Before hardening: it works. After: refused.) This single exercise justifies everything above.
2. **Read env vars in a pod** → observe your DB password sitting in plaintext. Motivates secret scoping and rotation.
3. **Apply a too-strict NetworkPolicy** → watch Outline lose the DB; practice the netcat debug flow.
4. **Verify CNI enforcement** → with Flannel, "blocked" traffic still flows. Feel the difference after switching to Cilium/Calico.
5. **Flip `enforce: restricted` prematurely** → watch a deploy get rejected; then do the warn→audit→enforce sequence properly.
6. **Rotate the DB password** → the full end-to-end drill; time it; automate what hurt.

---

## Exit criteria for M13

- [ ] Every app SA: no token mounted, no RoleBindings beyond none
- [ ] Jenkins SA scoped to its namespaces; `auth can-i` audit is clean
- [ ] CNI enforces NetworkPolicy (proven by test); database/cache/storage namespaces default-deny with explicit allows
- [ ] App namespaces at `restricted` (via warn→audit→enforce); Outline chart runs non-root, read-only rootfs
- [ ] No secret in Git or values; Sealed Secrets or ESO in place; etcd encryption at rest enabled
- [ ] Self-attack exercise: exec into a pod, fail to reach the API, fail to reach Postgres from a foreign namespace
- [ ] One rotation drill completed end-to-end

Next: `15-backup-dr` — assuming everything fails, and proving you can recover.
