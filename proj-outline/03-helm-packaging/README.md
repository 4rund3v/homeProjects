# 03 — Helm: Packaging and Releasing

**Folder:** `03-helm-packaging/`
**Milestone:** M3 (foundation), reused everywhere

---

## Teach first: why Helm exists

### The problem

By the end of doc 02 you'll have written a pile of YAML for a single app: Deployment, Service, Ingress, ConfigMap, Secret, PVC, ServiceAccount, maybe an HPA and a PDB. Now multiply that by every app on your platform. Then realize:

- **Environment differences.** Dev uses 1 replica and a tiny Postgres; prod uses 5 and a big one. Do you copy the YAML and edit? Now you have two files that drift.
- **Versioning.** How do you know what's deployed? How do you roll back? `kubectl apply` has no concept of "a release."
- **Templating.** The image tag changes every build. The hostname differs per environment. You can't hard-code these.
- **Reuse.** Every app needs the same boilerplate. Do you copy-paste it?

Helm answers all four: it's **templating + packaging + release management** for Kubernetes manifests.

### What Helm actually is

- **A chart** = a directory of templated manifests + a `values.yaml` + metadata.
- **A template** = a manifest with placeholders (`{{ .Values.image.tag }}`).
- **Values** = the concrete inputs that fill the placeholders.
- **A release** = one installed instance of a chart in a cluster, with its own name, revision history, and state.

```
chart (template)  +  values (inputs)  =  rendered manifests  →  release (deployed, versioned)
```

Helm stores each release's state **as a Secret in the cluster** (by default) or a ConfigMap. That's how it knows what it installed and can diff/rollback.

### The killer feature: rollback

```
helm upgrade outline ./chart -f prod.yaml   # revision 4
helm history outline                          # see all revisions
helm rollback outline 3                       # back to revision 3
```

`kubectl apply` cannot do this. This alone justifies Helm for anything stateful or user-facing.

---

## Why this fits *this* project

You'll use Helm for **every** component:

| Component | How |
|---|---|
| ingress-nginx, cert-manager | Official charts (or via Terraform Helm provider) |
| kube-prometheus-stack | Official chart — huge, teaches you to read big values files |
| CloudNativePG | Operator chart |
| Redis | Bitnami chart |
| MinIO | Official chart |
| Keycloak | Chart |
| Jenkins | Official chart + your JCasC values |
| Harbor | Official chart |
| **Outline** | **You write this chart yourself** — the payoff |

Writing the Outline chart yourself is the point. Reading charts teaches you to consume; writing one teaches you to think in templates, values, and release lifecycle.

---

## Chart anatomy

```
outline/
├── Chart.yaml          # name, version, appVersion, dependencies
├── values.yaml         # default inputs
├── templates/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   ├── secret.yaml     # careful — see below
│   ├── serviceaccount.yaml
│   ├── hpa.yaml
│   └── _helpers.tpl    # reusable template snippets
└── charts/             # subcharts (dependencies)
```

### `Chart.yaml` — the identity

```yaml
apiVersion: v2
name: outline
version: 0.1.0        # chart version — bump on chart changes
appVersion: "0.78.0"  # the app version this chart deploys
```

> **Senior lens** — `version` and `appVersion` are different things and both matter. `version` is the *chart's* semver; `appVersion` is the *application's* version. When you ship a new app release, you change `appVersion` (maybe). When you change the chart's logic, you bump `version`. Conflating them makes rollback reasoning impossible.

### The templating engine

Helm uses Go templates. The patterns you'll use constantly:

```
{{ .Values.image.repository }}:{{ .Values.image.tag }}
{{ .Release.Name }}
{{ .Release.Namespace }}
{{ .Chart.AppVersion }}
{{ include "outline.fullname" . }}    # from _helpers.tpl
```

Control flow:

```
{{- if .Values.ingress.enabled }}
# ... ingress yaml ...
{{- end }}

{{- range .Values.extraEnv }}
- name: {{ .name }}
  value: {{ .value }}
{{- end }}
```

> **Gotcha — whitespace.** The `{{-` and `-}}` trims matter. Without them you get stray blank lines and broken indentation in rendered YAML. Learn `helm template` early to see exactly what Helm produces.

### `_helpers.tpl` — DRY naming

Define reusable name logic once:

```
{{- define "outline.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
```

Then every resource uses `{{ include "outline.fullname" . }}` so names are consistent and stay within k8s's 63-char limit.

---

## Values: the interface of your chart

`values.yaml` is a **contract**. It defines every knob consumers can turn. Design it deliberately:

```yaml
replicaCount: 2

image:
  repository: harbor.lab.example/outline
  tag: ""              # empty → falls back to Chart.AppVersion
  pullPolicy: IfNotPresent

resources:
  requests: { cpu: 250m, memory: 512Mi }
  limits:   { cpu: "1",  memory: 1Gi }

postgres:
  host: postgres.database.svc.cluster.local
  # password comes from an existing secret, never here

ingress:
  enabled: true
  host: outline.lab.example
  tls: true

autoscaling:
  enabled: false
  minReplicas: 2
  maxReplicas: 6
```

> **Senior lens — never put secrets in `values.yaml`.** Values files get committed to Git. Pass secrets via `--set` from CI (from a secret store), or reference an existing Secret with `existingSecret:`. This is the #1 Helm security mistake.

### Layering values (the override chain)

Helm merges values in a defined order (later wins):

```
chart defaults (values.yaml)
  → -f base.yaml
  → -f environment.yaml      # lab.yaml / prod.yaml
  → --set key=value           # highest priority (use sparingly, for dynamic values like image tag)
```

This layering is how you get **one chart, many environments**: `values.yaml` (defaults) + `lab.yaml` (overrides) + `--set image.tag=$GIT_SHA` (per-build).

> **Tradeoff — `--set` vs. values files.** `--set` is convenient for dynamic, single values (image tags) but unreadable and error-prone for anything structural (nested lists are painful). **Use files for structure, `--set` only for a handful of truly dynamic values.** A pipeline full of `--set` flags is a code smell.

---

## Release lifecycle and the three-way merge

This is where Helm gets subtle and where seniors separate from juniors.

Helm's upgrade is a **three-way merge**:

```
old manifest (what's deployed)  +  new chart output  +  live cluster state
```

> **Why this matters** — if you `kubectl edit` a resource that Helm manages, Helm's next upgrade may revert it (because Helm doesn't know about your edit) or keep it (if the field is "unchanged"). This out-of-band editing is called **drift**, and Helm isn't fully drift-aware the way GitOps is. Rule: **if Helm manages it, change it via Helm, not `kubectl`.**

### Upgrade strategies

- **`helm upgrade`** — replaces changed resources. Combined with a Deployment's rolling update, gives zero-downtime.
- **`--atomic`** — if the upgrade fails, automatically roll back. **Use this in CI.**
- **`--wait`** — block until resources are ready. Essential for ordering; without it your pipeline "succeeds" before pods are actually up.
- **`--timeout`** — how long to wait.

> **Senior lens** — in a CD pipeline, use `helm upgrade --install --atomic --wait --timeout 5m`. `--install` makes it idempotent (install if absent, upgrade if present), `--atomic` gives automatic rollback on failure, `--wait` prevents the pipeline from reporting success prematurely. This one line encodes a surprising amount of operational maturity.

---

## Hooks — ordering within a release

Sometimes you need something to run *before* the app deploys (a DB migration) or *after* (a smoke test). Helm **hooks** do this:

| Hook | Runs |
|---|---|
| `pre-install` / `pre-upgrade` | Before resources are created/updated (migrations) |
| `post-install` / `post-upgrade` | After resources are ready (smoke tests) |
| `pre-delete` | Before uninstall (cleanup) |
| `test` | On `helm test` (verification) |

Hooks are implemented as Jobs/Pods annotated with `helm.sh/hook`.

> **Tradeoff — hooks vs. init containers vs. separate migration Job.** Helm hooks are convenient but tie migration logic to the release lifecycle and can be fiddly (a failed hook can leave the release in a weird state). Many teams prefer running migrations as a **separate, explicit Job** in the CD pipeline so the "migrate" and "deploy" steps are independently observable and retryable. Note both; start with hooks, graduate to explicit jobs as you mature.

---

## Dependencies and subcharts

A chart can depend on other charts (`Chart.yaml` `dependencies:` + `helm dependency update`). This is how you bundle "Outline + a Redis sidecar chart" as one release.

> **Tradeoff — subcharts vs. independent releases.** Subcharts give you atomic versioning (one release, one rollback). But they couple lifecycles — you can't upgrade Redis independently of Outline, and a values conflict between parent and child is confusing. **For shared infrastructure (Postgres, Redis, MinIO) prefer independent releases**; use subcharts only when the dependency genuinely ships together.

---

## Repositories, OCI, and packaging

- **Classic repos** — an HTTP index of `.tgz` chart packages.
- **OCI registries** — charts pushed to a registry like `oci://harbor.lab.example/charts/outline`. This is the modern path and **integrates with your Harbor** (doc 05).

```
helm package outline/                       # → outline-0.1.0.tgz
helm push outline-0.1.0.tgz oci://harbor.lab.example/charts
helm install outline oci://harbor.lab.example/charts/outline --version 0.1.0
```

> **Senior lens** — treating charts as versioned OCI artifacts in the same registry as your images gives you **one artifact repository, one retention policy, one access control**. This is cleaner than a separate chart repo and reinforces the Harbor work in doc 05.

---

## The workflow you'll live in

```
helm lint ./outline                    # static checks
helm template outline ./outline -f lab.yaml   # render locally, inspect YAML
helm diff upgrade outline ./outline -f lab.yaml   # what WOULD change (plugin)
helm upgrade --install outline ./outline -f lab.yaml --atomic --wait
helm history outline
helm rollback outline <revision>
helm uninstall outline
```

> **`helm diff`** is a plugin, not built-in, and it's **essential**. It's the Helm equivalent of `terraform plan`. A CD pipeline that doesn't show a diff before applying is flying blind.

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| Chart vs. plain manifests | Chart as soon as you have >1 environment or need rollback |
| `--set` vs. values files | Files for structure; `--set` only for dynamic single values |
| `--atomic`/`--wait` | Always in CI; never let a pipeline report success prematurely |
| Secrets location | Never in values files; use existing Secrets or a secret manager |
| Subcharts vs. separate releases | Separate releases for shared infra; subcharts for truly-coupled bundles |
| Chart storage | OCI in Harbor — one registry, one policy |
| Hooks vs. explicit Jobs | Hooks to start; explicit migration Jobs as you mature |

---

## Failure modes you must deliberately cause

1. **Break a template** (bad indentation) → `helm template` and `helm lint` catch it before deploy.
2. **Deploy with a bad image tag** → `--atomic` rolls back automatically; observe it.
3. **Skip `--wait`** → pipeline "succeeds" while pods are still crashing; now you know why `--wait` matters.
4. **Edit a Helm-managed resource with `kubectl`** → next upgrade reveals the drift behavior.
5. **Roll back** a release → confirm the previous revision's state is restored exactly.
6. **Pass a secret via `--set`** → find it in `helm get values` output in the cluster; learn why values are readable.

---

## Exit criteria for M3

- [ ] You've written a working Outline chart with a clean `values.yaml` contract
- [ ] You can deploy the same chart to two environments with different values
- [ ] You understand `helm diff` and use it before every upgrade
- [ ] You can roll back and explain what revision state means
- [ ] Your chart is packaged and pushed to Harbor as an OCI artifact
- [ ] No secrets are stored in any values file

Next: `04-jenkins-cicd` — automating the build and deploy.
