# Ingress NGINX on k3s

> How the ingress-nginx controller turns Kubernetes objects into nginx config, how to
> debug what it generated, and where the common route-not-working bugs live.

---

## 1. The pieces

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │                                                                       │
  │   CONTROL PLANE (k3s)                                                │
  │   ┌──────────────────────────────────────────────────────────┐       │
  │   │  Ingress resource         IngressClass resource           │       │
  │   │  ─ route rules ─         ─ "which controller?" ─         │       │
  │   └──────────────┬───────────────────┬────────────────────────┘       │
  │                  │ watches           │                                │
  │   ┌──────────────▼───────────────────▼────────────────────────┐       │
  │   │         ingress-nginx controller (a Deployment, 2+        │       │
  │   │         replicas with leader election)                     │       │
  │   │                                                            │       │
  │   │         • watches Ingresses, Services, EndpointSlices      │       │
  │   │         • renders nginx.conf                               │       │
  │   │         • ships it to the nginx workers via a SharedVolume│       │
  │   │         • reloads the master (SIGHUP)                      │       │
  │   └───────────────────────────────────────────────────────────┘       │
  │                                                                       │
  │   ┌──────────────────────────────────────────────────────────┐       │
  │   │  nginx master + workers  (an nginx instance inside a Pod) │       │
  │   │  • listening on :80 / :443                               │       │
  │   │  • the config it serves IS what the controller rendered   │       │
  │   └──────────────────────────────────────────────────────────┘       │
  └──────────────────────────────────────────────────────────────────────┘
```

**The mental model:** an Ingress object is *not* executed. It's *data*. A controller
reads all Ingresses and compiles them into a real `nginx.conf`, then reloads nginx.
When debugging, always ask: **what did the controller actually generate?**

---

## 2. The CRDs

### IngressClass — which controller handles it

```yaml
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: nginx
spec:
  controller: k8s.io/ingress-nginx
  default: true        # optional: mark as the default
```

### Service — what's behind it

```yaml
apiVersion: v1
kind: Service
metadata:
  name: expense-api
spec:
  selector:
    app: expense-api     # ← must match the pod labels, or no endpoints
  ports:
    - port: 80           # service port
      targetPort: 8000   # ← pod port; must match the containerPort
```

### Ingress — the routing rule

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
spec:
  ingressClassName: nginx
  tls:
    - hosts: [api.example.com]
      secretName: api-tls           # ← the TLS Secret (see ../tls/)
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: expense-api
                port:
                  number: 80
```

---

## 3. `host` vs `path` routing

```
  RULE: api.example.com + /api → expense-api
  RULE: api.example.com + /     → ui

  Incoming request:
  ┌─────────────┬────────────┬──────────────────────────────────┐
  │ Host header │   path     │        matches                    │
  ├─────────────┼────────────┼──────────────────────────────────┤
  │ api.ex.co   │ /api/v1/x  │ → expense-api                      │
  │ api.ex.co   │ /login     │ → ui                               │
  │ other.co    │ /api       │ → default backend (404)            │
  └─────────────┴────────────┴──────────────────────────────────┘
```

**`pathType` semantics (v1 Ingress):**

| Type | Meaning |
|------|---------|
| `Exact` | the path must match exactly |
| `Prefix` | the path matches on `/`-segment boundaries (a prefix of `/api/` also matches `/api/v1/foo`, but `/api-v2` does not) |
| `ImplementationSpecific` | controller decides |

**Gotcha:** with `Prefix` and a `rewrite-target` annotation, the rewrite applies
after matching. Two `Prefix` locations with overlapping paths can behave unexpectedly —
be specific about ordering or use distinct top-level paths.

---

## 4. Reading the rendered config (the #1 debugging skill)

```
  ┌───────────────────────────────────────────────────────────────┐
  │  YOUR Ingress annotations  ──►  controller  ──►  rendered     │
  │                                                        nginx.conf│
  │                                                                │
  │  If routing is broken, ALWAYS look at the rendered config.     │
  │  The rendered file is ground truth.                            │
  └───────────────────────────────────────────────────────────────┘
```

```bash
# 1. Find the ingress-nginx controller pod
kubectl -n ingress-nginx get pods -l app.kubernetes.io/name=ingress-nginx

# 2. Dump the FULL rendered config from inside the controller
kubectl -n ingress-nginx exec -it <pod> -- nginx -T 2>/dev/null \
    | grep -A5 'server_name api.example.com'

# 3. Or look at the generated configmap (some deployments expose it)
kubectl -n ingress-nginx get configmap | grep -i nginx
```

What to look for in the output:

- Is the `server` block present? If not, the Ingress wasn't matched.
- Does `proxy_pass` point at the right Service? Does it have a trailing slash?
- Are the `ssl_certificate` and `ssl_certificate_key` paths pointing at files that
  exist? (`kubernetes.io/ingress-tls` secrets are mounted automatically.)
- Is `listen 443 ssl http2;` present if you expect TLS?

**Common rendered-config bugs:**

```
  Annotation typo
    nginx.ingress.kubernetes.io/proxy-body-size  ✓
    nginx.ingress.kubernetes.io/proxy_body_size  ✗ silently ignored

  → The config looks identical to before. Debugging is hours of guessing.

  IngressClass not specified
    spec:
      ingressClassName: nginx     ← must be present (or default IngressClass set)

  → Ingress sits there, controller doesn't own it, nothing is rendered.

  Wrong Service port
    backend.service.port.number: 8000   ← this is the SERVICE port
                                           (must be 80 per Service spec, not podPort)

  → 503 Service Unavailable from nginx.
```

---

## 5. EndpointSlices and when a route suddenly works/stops

```
  Pod created  ──►  passes readiness  ──►  added to EndpointSlice
                                             │
                                             ▼
                                     controller regenerates nginx.conf
                                             │
                                             ▼
                                     reload (SIGHUP) → nginx knows
```

**Symptoms of EndpointSlice issues:**

- Pod is Running but no traffic reaches it → readiness probe failing, or the Service
  `selector` doesn't match the pod labels.
- Traffic works, then stops after deploy → the new pod didn't pass readiness yet
  (correct behavior, but confusing if you didn't know).
- `kubectl get endpoints expense-api` shows empty → the Service is orphaned; pods
  exist but nothing selects them.

```bash
kubectl get endpointslices -l kubernetes.io/service-name=expense-api -o yaml
kubectl get svc expense-api -o yaml      # check the selector
kubectl get pods --show-labels           # check the pod labels
```

---

## 6. TLS annotations and secrets

TLS mechanics live in [`../tls/`](../tls/). The Ingress-specific part:

```yaml
metadata:
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-dns01   # if using cert-manager
spec:
  tls:
    - hosts: [api.example.com]
      secretName: api-tls
```

cert-manager watches this `tls` block, issues/renews the cert, and writes it to the
`api-tls` Secret. nginx mounts that Secret and serves it — the mechanics of which are
in [`../tls/operational.md`](../tls/operational.md).

**The cert not showing up in a browser?** Check the Secret actually exists and is
mounted:

```bash
kubectl -n ingress-nginx get secret api-tls -o jsonpath='{.metadata.annotations}'
kubectl -n ingress-nginx get secret api-tls -o yaml | head
```

---

## 7. `allow-snippet-annotations` — a real security escalation

```yaml
metadata:
  annotations:
    nginx.ingress.kubernetes.io/configuration-snippet: |
      more_set_headers "X-Custom: $remote_addr";
```

This lets an Ingress author inject raw nginx directives. It's the equivalent of
**arbitrary nginx code execution** for whoever can create an Ingress.

**Default should be OFF.** Anyone who can create an Ingress in your cluster is not a
trusted admin. When enabled, they can:

- read arbitrary nginx variables and log sensitive data
- inject a `proxy_pass` pointing anywhere (SSRF against internal services)
- disable rate limiting on their route

If you need custom headers, use first-class annotations
(`proxy-set-headers`, `configuration-annotation`, etc.) rather than a snippet. Only
turn this on with a tight RBAC policy.

---

## 8. Leader election and rolling deploys

The controller runs as multiple replicas for HA. Only **one** is the leader at a time
(elected via a Kubernetes Lease); the leader is the only one that regenerates config.
When the leader dies, another takes over in seconds.

**Rolling a new ingress-nginx image:** the leader change may drop the "active" controller
briefly. The nginx workers keep serving from the last generated config — no route is
lost. This is why ingress-nginx is safe to roll.

---

## 9. Interview angle

- **"How does ingress-nginx work?"** — a controller watches Ingress/Service/
  EndpointSlice objects, renders `nginx.conf`, ships it to the nginx master and
  reloads.
- **"Routing isn't working. First step?"** — dump the rendered config
  (`nginx -T`) and check it, not the Ingress object. Then check the Service selector
  and pod labels.
- **"What is an EndpointSlice?"** — the k8s primitive holding the current set of pod
  IPs backing a Service. The controller regenerates its upstreams from these.
- **"Is allow-snippet-annotations safe?"** — no, it's arbitrary nginx config injection.
  Off by default; only with tight RBAC.

---

## 10. How this shows up here

- The `/api` and `/ui` routing on `api.example.com` is exactly the two Ingress
  examples above.
- The rendered-config workflow (`nginx -T`) is the diagnostic for the runbook in
  [`../runbooks.md`](../runbooks.md).
- cert-manager + Ingress TLS is the integration point between this doc and
  [`../tls/this-project-topology.md`](../tls/this-project-topology.md).
- With one node, you don't run multiple controller replicas — one is enough, but the
  leader-election model means adding more is safe.
