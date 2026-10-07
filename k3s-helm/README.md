# k3s and Helm

**Goal:** Deploy services already understood locally, then observe Kubernetes lifecycle behavior.

**Scope:** Single-node local k3s, Deployments, Services, ConfigMaps/Secrets, probes, resource limits, Helm charts, rolling updates.

**Out of scope:** Cloud-managed clusters, service meshes, and production secrets management.

**Learning focus:** Desired state, scheduling basics, readiness vs. liveness, rollout behavior, chart values, debugging pods and events.

**Depends on:** `go-http-server` and `telemetry-hub`; deploy `keycloak-setup` after it exists.

## Milestones
- [ ] Bring up local k3s and deploy a minimal service.
- [ ] Package `telemetry-hub` with a Helm chart.
- [ ] Add probes and observe recovery from a failing container.
- [ ] Perform a rolling update and inspect rollout status/history.
- [ ] Handle secrets locally without committing credentials.
