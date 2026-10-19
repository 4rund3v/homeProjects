# Values.yaml vs. ConfigMap vs. Secrets — What Goes Where

**Companion to:** `03-helm-packaging/README.md`

You asked a really good question that trips up everyone writing their first chart:

> *What goes in `values.yaml`? What goes in a ConfigMap? What goes in a Secret? Do I have to put everything in values?*

The short answer: **`values.yaml` is the chart's input interface; ConfigMap and Secret are Kubernetes resources rendered from it.** They're not alternatives — they're different layers. Everything a consumer should be able to change gets a value key. The chart's *templates* then decide which of those values become a ConfigMap, which become a Secret, and which get injected directly into a Deployment (env vars, args, resources).

There is no official spec, because Helm deliberately doesn't prescribe chart structure. But the community has strong conventions that, once you learn them, make every chart feel natural. This document codifies them.

---

## The mental model: three layers

```
values.yaml           ← INPUT. Consumer-facing knobs. Not a k8s resource.
     │
     │ (Helm renders)
     ▼
templates/*.yaml      ← LOGIC. Decides what becomes what.
     │
     ▼
k8s resources         ← OUTPUT. ConfigMap, Secret, Deployment, Service, PVC...
```

- **values.yaml** — the contract with whoever `helm install`s your chart.
- **templates** — the transformation logic (YAML with Go templates).
- **k8s resources** — what actually lands in the cluster.

**A value becomes a ConfigMap, a Secret, an env var, or a Deployment field — but only because a template says so.** values.yaml itself doesn't declare "this is a configmap"; the templates do.

---

## The core rule

> **Everything a consumer must be able to change goes in `values.yaml`.**
> **A ConfigMap or Secret is the rendered *destination* for some of those values, not a place where you bypass values.**

So: yes, you define `database.host`, `database.port`, `database.username` in `values.yaml`. The template decides:
- `host`, `port`, `username` → go into a ConfigMap (they're not sensitive).
- `password` → goes into a Secret.

The values live in one place (values.yaml). The templates scatter them to the right resources.

> **Senior lens** — if you can point at a k8s manifest and say "that value came from `values.yaml` key X," you understand the chart. If a value appears in a template but not in values.yaml, it's either (a) hard-coded (bad) or (b) a template default (better) or (c) derived (`.Release.Name`, `.Chart.AppVersion` — fine). Every "why is this here?" question in a chart should resolve to a values key.

---

## The top-level hierarchy you keep seeing (two tiers, four kinds)

You'll open a chart and see a wall of top-level blocks — `image`, `resources`, `ingress`, `appConfig`, `serviceConfig`, `otel_config`, `database`, `redis`, `storage`, `logging`, `metrics`… Is there a standard order or menu? **No official spec.** But there is a strong, learnable convention, and it has two tiers.

### Tier 1 — the "Helm-standard" blocks

These describe **k8s-native plumbing** (the pod, the Service, the Ingress, the HPA) — *not* the application. They are near-identical across every mature chart (bitnami, CloudNativePG, ingress-nginx, grafana, harbor), so you'll recognize them by reflex:

```
image:            { repository, tag, pullPolicy }
imagePullSecrets:
replicaCount:
revisionHistoryLimit:
resources:        { requests, limits }
serviceAccount:
podSecurityContext: / securityContext:
probes:           { liveness, readiness, startup }
nodeSelector / tolerations / affinity
persistence / storage
service:          { type, port, annotations }
ingress:          { enabled, className, hosts, tls }
networkPolicy:
autoscaling:      { enabled, minReplicas, maxReplicas, targetCPU... }
```

> **Why this tier feels "standard"** — it's convention by pure repetition, not by spec. Because every serious chart is laid out the same way, you can read a chart you've never seen. This tier is the one you should *copy the shape of* from a reference chart (ingress-nginx and bitnami are the best templates).

### Tier 2 — app-specific blocks (your `app_config`, `otel_config`, …)

These mirror **the application's own** config surface. The names are *chart-author + app-specific*: `otel_config` exists because that app exposes `OTEL_*` env vars; `database` exists because it talks to Postgres. **There is no standard for this tier — you read it off the app, not off a spec.**

But even without a spec, tier-2 blocks cluster into **four recurring kinds**. That taxonomy is the real "hierarchy":

| Kind | Examples | What it is |
|---|---|---|
| **Dependencies** — app talks *to* | `database`, `redis`, `storage`, `smtp`, `oidc`/`authentication` | external systems; values are connection details |
| **Behavior** — what the app *does* | `appConfig`, `serviceConfig`, `featureFlags`, `limits` | the app's own feature/logic settings |
| **Observability** | `otel_config`, `logging`, `metrics`, `tracing` | instrumentation knobs |
| **Network/edge** — how it's reached | `ingress`, `service`, `tls`, `networkPolicy` | often merged up into tier 1 |

### The rule that makes it stop feeling random

> **Name tier-2 blocks after the app's own config namespaces, grouped by kind.**

For your Outline chart the skeleton falls out of that rule:

```yaml
# ── Tier 1: k8s plumbing (copy shape from a reference chart) ──
image:
replicaCount:
resources:
serviceAccount:
probes:
persistence:
ingress:
networkPolicy:
autoscaling:

# ── Tier 2, kind "dependencies" ──
database:      # doc 06
redis:         # doc 07
storage:       # doc 08 (MinIO / S3)
oidc:          # doc 09 (Keycloak)

# ── Tier 2, kind "behavior" ──
app:           # PUBLIC_URL, SERVER_URL, HOSTNAME, LOCALE, …

# ── Tier 2, kind "observability" ──
otel_config:   # OTEL_* knobs (only if Outline ships them)
logging:
metrics:

# ── Tier 2, escape hatches ──
configMap: { extra: {} }   # the open map
extraEnv / extraVolumes / extraLabels
```

### The key distinction (re-stated for this tier)

A tier-2 block is **not** a "ConfigMap block" or a "Secret block." The *block name* tells you the app's grouping; **the template decides where it lands in k8s.** A non-sensitive `otel_config` renders into the app's ConfigMap; a sensitive one renders into a Secret; `database` *splits* — `host`/`database`/`user` go to the ConfigMap, `password` goes to the Secret. The block is the app's lens; the destination is the k8s lens.

---

## What actually belongs where

### `values.yaml` — the input surface

Every knob a consumer needs. Grouped logically:

```yaml
# ── deployment ──
replicaCount: 2

image:
  repository: harbor.lab.example/outline
  tag: ""              # empty → falls back to Chart.AppVersion
  pullPolicy: IfNotPresent

resources:
  requests:
    cpu: 250m
    memory: 512Mi
  limits:
    cpu: "1"
    memory: 1Gi

# ── application config (non-sensitive) ──
app:
  publicUrl: https://outline.lab.example
  serverUrl: https://api.outline.lab.example
  locale: en

# ── sensitive config (values are placeholders / references) ──
secrets:
  existingSecret: outline-secrets      # reference an existing Secret by name
  # OR define them here and let the chart create the Secret:
  appSecret: ""
  databaseUrl: ""
  redisUrl: ""

# ── database (reference, not ownership — Outline connects to external PG) ──
database:
  host: postgres.database.svc.cluster.local
  port: 5432
  database: outline
  user: outline
  # password comes from the Secret above, never from values.yaml directly
  existingSecretKey: password

# ── ingress ──
ingress:
  enabled: true
  className: nginx
  annotations: {}
  hosts:
    - host: outline.lab.example
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: outline-tls
      hosts: [outline.lab.example]

# ── autoscaling ──
autoscaling:
  enabled: false
  minReplicas: 2
  maxReplicas: 6
  targetCPUUtilizationPercentage: 75

# ── extra stuff (escape hatches) ──
extraEnv: []              # arbitrary env vars
extraVolumes: []          # arbitrary volumes
extraVolumeMounts: []
extraLabels: {}
```

Notice: **sensitive values reference an existing Secret** (`existingSecret: outline-secrets`). The chart doesn't create the Secret; your external secret store (Sealed Secrets, External Secrets, or Jenkins credentials) does. This is the *secure* pattern.

The *less secure* but simpler pattern is to let the chart create the Secret from values:

```yaml
secrets:
  appSecret: "some-strong-random-string"   # ❌ this lands in Git!
```

Never commit real secrets to values.yaml. If you use the chart-created-Secret pattern, the values file itself must be uncommitted (e.g. a `values.local.yaml` in `.gitignore`) or the secrets must be injected at install time via `--set` from a secret store in CI.

---

### ConfigMap — rendered, non-sensitive app config

A ConfigMap is what an *application* reads as env vars or files. It's rendered from values by a template. **You don't put config "in the ConfigMap" and "in values" — you put it in values, and the template renders it into a ConfigMap.**

```yaml
# templates/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "outline.fullname" . }}
  labels: {{- include "outline.labels" . | nindent 4 }}
data:
  PUBLIC_URL:  {{ .Values.app.publicUrl | quote }}
  SERVER_URL:  {{ .Values.app.serverUrl | quote }}
  LOCALE:      {{ .Values.app.locale    | quote }}
  DATABASE_URL: "postgres://{{ .Values.database.user }}@{{ .Values.database.host }}:{{ .Values.database.port }}/{{ .Values.database.database }}"
```

Then the Deployment references the ConfigMap:

```yaml
# templates/deployment.yaml
envFrom:
  - configMapRef:
      name: {{ include "outline.fullname" . }}
```

**Everything in the ConfigMap came from `values.yaml`** — the template just decided "these are non-sensitive, so they go in a ConfigMap rather than a Secret."

---

### Secret — rendered, sensitive app config

Same idea, different destination:

```yaml
# templates/secret.yaml
apiVersion: v1
kind: Secret
type: Opaque
metadata:
  name: {{ include "outline.fullname" . }}
data:
  APP_SECRET: {{ .Values.secrets.appSecret     | b64enc | quote }}
  REDIS_URL:  {{ .Values.secrets.redisUrl      | b64enc | quote }}
```

The Deployment pulls sensitive env from the Secret:

```yaml
envFrom:
  - configMapRef:
      name: {{ include "outline.fullname" . }}
  - secretRef:
      name: {{ include "outline.fullname" . }}
```

> **The two patterns for secrets**
>
> **Pattern A — chart creates the Secret from values:** Simple, but values.yaml (or an override file) contains the secrets, so that file must not be committed. Common in dev, discouraged in prod.
>
> **Pattern B — chart references an existing Secret:** The chart has `existingSecret: outline-secrets` in values, and the template uses `secretRef: { name: outline-secrets }`. **The chart never sees the secret value.** This is the production pattern. External Secrets Operator or Sealed Secrets creates that Secret outside Helm.
>
> For this project, use Pattern B for prod, Pattern A for local dev convenience.

---

## The "open map" vs. "explicit fields" decision

Here's the design question underneath yours:

- **Explicit fields** — every config key is a named value (`app.publicUrl`, `app.locale`, `app.serverUrl`).
- **Open map** — a bag of config (`app.config: { anything: goes }`) that the template dumps into a ConfigMap with `toYaml`.

### Explicit (good for small, stable, well-known config)

```yaml
# values.yaml
app:
  publicUrl: https://...
  locale: en
```

```yaml
# templates/configmap.yaml
data:
  PUBLIC_URL: {{ .Values.app.publicUrl | quote }}
  LOCALE:     {{ .Values.app.locale | quote }}
```

**Pros:** self-documenting, discoverable, type-safe-ish, IDE completion if you provide JSON Schema. **Cons:** you must update the chart every time the app adds a config key.

### Open map (good for large, dynamic config)

```yaml
# values.yaml
configMap:
  extra:
    FEATURE_X: "on"
    LOG_LEVEL: "info"
```

```yaml
# templates/configmap.yaml
{{- toYaml .Values.configMap.extra | nindent 2 }}
```

**Pros:** zero chart changes when the app adds keys. **Cons:** no discoverability, no schema, typos surface at runtime not at render time.

### The hybrid (what real charts use)

Use **explicit** for the handful of important, stable settings (image, replicas, resources, ingress, DB connection) — because consumers need to find them. Use **open map** for the long tail of feature flags and app-specific knobs — because the app's author is the only one who knows what they'll add next.

> **Senior lens** — outline ships a large `env` surface (see `outline/env.js` in the Outline repo). Explicit-only for all of it would mean updating the chart on every Outline release. The right shape: **explicit for the ~10 things every deployment needs** (`PUBLIC_URL`, `DATABASE_URL`, `REDIS_URL`, `APP_SECRET`, `SECRET_KEY`, `SERVER_URL`, `HOSTNAME`), **open map for everything else.** That's a judgment call, and it's the kind of judgment call the doc 03 README was missing.

### Concrete example: Outline's actual chart shape

```yaml
# values.yaml — explicit for the important stuff
app:
  publicUrl: https://outline.lab.example
  serverUrl: https://api.outline.lab.example
  hostname: outline.lab.example
  locale: en

database:
  host: postgres.database.svc.cluster.local
  port: 5432
  database: outline
  user: outline

redis:
  host: redis.cache.svc.cluster.local
  port: 6379

secrets:
  existingSecret: outline-secrets     # Pattern B — secrets live elsewhere

# open map for the long tail
configMap:
  extra:
    STORAGE_URI: "s3://outline-files"
    STORAGE_BASE_URL: "https://minio.lab.example/outline-files"
    LOG_LEVEL: "info"
    NODE_ENV: "production"
```

```yaml
# templates/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "outline.fullname" . }}
data:
  PUBLIC_URL:   {{ .Values.app.publicUrl   | quote }}
  SERVER_URL:   {{ .Values.app.serverUrl   | quote }}
  HOSTNAME:     {{ .Values.app.hostname    | quote }}
  LOCALE:       {{ .Values.app.locale      | quote }}
  DATABASE_URL: "postgres://{{ .Values.database.user }}@{{ .Values.database.host }}:{{ .Values.database.port }}/{{ .Values.database.database }}"
  REDIS_URL:    "redis://{{ .Values.redis.host }}:{{ .Values.redis.port }}"
{{- with .Values.configMap.extra }}
{{- toYaml . | nindent 2 }}
{{- end }}
```

Everything in the ConfigMap traces back to a `values.yaml` key. That's the invariant.

---

## What goes in each layer — the decision table

| Kind of value | values.yaml? | ConfigMap? | Secret? | Notes |
|---|---|---|---|---|
| Image repo/tag | ✅ | ❌ | ❌ | Consumed by Deployment |
| Resource requests/limits | ✅ | ❌ | ❌ | Deployment field |
| Replicas | ✅ | ❌ | ❌ | Deployment field |
| Ingress host/path/TLS | ✅ | ❌ | ❌ | Ingress resource |
| Non-sensitive app env | ✅ | ✅ (rendered) | ❌ | Template → ConfigMap |
| Sensitive app env (Pattern A) | ✅ (uncommitted) | ❌ | ✅ (rendered) | Template → Secret |
| Sensitive app env (Pattern B) | ✅ (name of existing Secret) | ❌ | ✅ (external) | Template → secretRef |
| Existing k8s names (e.g. `serviceAccountName`) | ✅ | ❌ | ❌ | Deployment field |
| Kubernetes-specific fields (labels, annotations) | ✅ | ❌ | ❌ | Injected into resources |
| Arbitrary app config (feature flags, URLs) | ✅ (open map) | ✅ (rendered) | ❌ | Template → ConfigMap |
| Certificates/private keys | ❌ | ❌ | ✅ (external) | TLS Secret, managed by cert-manager |
| kubeconfig for internal calls | ❌ | ❌ | ✅ (external) | Sealed Secrets / External Secrets |

The pattern: **values.yaml is the input, everything else is output.**

---

## Anti-patterns to avoid

### ❌ Hard-coding values in templates

```yaml
# templates/deployment.yaml
resources:
  requests:
    cpu: 500m          # ❌ hard-coded; must be in values
```

```yaml
# ✅
resources: {{- toYaml .Values.resources | nindent 6 }}
```

### ❌ Duplicating a value in both a ConfigMap and a Secret

If `PUBLIC_URL` is in both, they can drift. Every value has one home.

### ❌ Putting secrets in a ConfigMap

ConfigMaps are readable by anyone with namespace access. Secrets aren't encrypted by default (see doc 02), but at least RBAC can restrict them. Putting a password in a ConfigMap is not "obfuscation."

### ❌ Making consumers edit templates to change config

If someone has to edit `templates/configmap.yaml` to add a config key, the chart is bad. That change should be a values key.

### ❌ `--set` for structural values

`--set app.publicUrl=https://...` is fine for one value. `--set ingress.hosts[0].paths[0].path=/` is unreadable. Use files for structure.

### ❌ Letting the chart create Secrets in prod

If your chart's `templates/secret.yaml` gets rendered in prod with real secrets, those secrets are in the rendered manifest (and potentially in CI logs). Use Pattern B for prod.

---

## The senior engineer's checklist for a new chart

Before you ship a chart, you can validate it against:

- [ ] Every k8s resource value traces to a `values.yaml` key (except derived from `.Release.*` / `.Chart.*`).
- [ ] Sensitive values use Pattern B (`existingSecret`) or an uncommitted values file — never committed to Git.
- [ ] `values.yaml` is well-commented: each key has a one-line doc, defaults make sense for a dev environment.
- [ ] The chart includes a **JSON Schema** (`values.schema.json`) that validates `values.yaml`. `helm lint --set ...` and `helm install --values-file` both check it. This catches typos at install time, not at runtime.
- [ ] There's a **README.md in the chart** documenting every values key (generated by `helm-docs` from YAML comments — see below).
- [ ] `helm template` renders cleanly; no secrets leak into rendered manifests in prod.
- [ ] `helm diff upgrade` shows a reasonable diff for a config change.

> **`helm-docs`** is a tool that reads YAML comments in `values.yaml` and generates a values reference table in the chart's README. Comment every key, run `helm-docs`, and you get documented values for free:
>
> ```yaml
> # Public URL of the Outline instance.
> #
> # @default https://example.com
> app:
>   publicUrl: https://example.com
> ```

---

## Putting it all together — a real Outline values.yaml, annotated

```yaml
# ── chart identity (consumed by templates) ──
replicaCount: 2                    # default; prod overrides to 4+
revisionHistoryLimit: 5            # bound Deployment's rollout history

# ── image ──
image:
  repository: harbor.lab.example/outline
  tag: ""                          # empty → .Chart.AppVersion
  pullPolicy: IfNotPresent

# ── image pull auth ──
imagePullSecrets:
  - harbor-creds                   # created in k8s by Jenkins

# ── resources ──
resources:
  requests: { cpu: 250m, memory: 512Mi }
  limits:   { cpu: "1",   memory: 1Gi }

# ── app config (non-sensitive → ConfigMap) ──
app:
  publicUrl: https://outline.lab.example
  serverUrl: https://api.outline.lab.example
  hostname: outline.lab.example
  locale: en

# ── database (external, not managed by this chart) ──
database:
  host: postgres.database.svc.cluster.local
  port: 5432
  database: outline
  user: outline
  # password: comes from the Secret below, never here

# ── redis ──
redis:
  host: redis.cache.svc.cluster.local
  port: 6379

# ── secrets (Pattern B: reference external Secret) ──
secrets:
  existingSecret: outline-secrets
  existingSecretKeys:              # map our env names to keys in that Secret
    APP_SECRET:     app_secret
    DATABASE_URL:   database_url   # built from db fields + password in external secret
    REDIS_URL:      redis_url
    STORAGE_SECRET: storage_secret # s3 creds

# ── storage (non-sensitive parts) ──
storage:
  bucket: outline-files
  region: us-east-1

# ── ingress ──
ingress:
  enabled: true
  className: nginx
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: "25m"
  hosts:
    - host: outline.lab.example
      paths: [{ path: /, pathType: Prefix }]
  tls:
    - secretName: outline-tls      # managed by cert-manager
      hosts: [outline.lab.example]

# ── persistence (Outline has a temp dir; usually no PVC needed) ──
persistence:
  enabled: false                   # Outline uses external S3 for uploads
  # size: 5Gi

# ── autoscaling ──
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 6
  targetCPUUtilizationPercentage: 75

# ── probes ──
probes:
  liveness:  { path: /health,    initialDelaySeconds: 30 }
  readiness: { path: /ready,     initialDelaySeconds: 10 }

# ── escape hatches ──
configMap:
  extra:                           # open map for app-specific long-tail config
    STORAGE_URI: "s3://outline-files"
    STORAGE_BASE_URL: "https://minio.lab.example/outline-files"
    LOG_LEVEL: "info"
    NODE_ENV: "production"
extraEnv: []                       # []
extraVolumes: []                   # []
extraVolumeMounts: []              # []
extraLabels: {}
annotations: {}
```

Every single k8s field this chart will emit — the Deployment's env, the ConfigMap's data, the Ingress's host, the Service's port — comes from a value key. The templates decide the destination; values are the source.

---

## Answering the original question directly

> *Is there a documentation on what should be in config-map, what should be in the values.yaml?*

- **There is no single official spec** — Helm doesn't prescribe chart structure.
- **The convention** (used by Bitnami, Harbor, ingress-nginx, kube-prometheus-stack, and every other well-regarded chart):
  - `values.yaml` holds *every consumer-facing knob*.
  - Templates render subsets into ConfigMap (non-sensitive), Secret (sensitive), or directly into the resource field (image, resources, replicas).
  - Secrets either come from an external source via `existingSecret` (Pattern B, prod-safe) or from an uncommitted values file / `--set` at install time (Pattern A, dev-friendly).
- **Rule of thumb:**
  - If the consumer must change it → values key.
  - If it's non-sensitive app config → ConfigMap (rendered from values).
  - If it's sensitive app config → Secret (referenced or rendered).
  - If it's k8s plumbing (resources, image, replicas, probes) → Deployment field (from values).

> **How to apply** — when you write your first Outline chart, follow the annotated `values.yaml` above. Then, when you encounter a config key the app needs, ask: *"do I add a values key, or does it go in the open `configMap.extra` map?"* Small/stable/important → values key. Long tail / app-specific → open map. That decision is where the craft lives.
