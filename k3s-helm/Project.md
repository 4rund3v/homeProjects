# k3s and Helm

## What this project exists to solve
Learn Kubernetes and Helm by deploying services already understood locally. The project reinforces operational thinking: desired state, probes, rollouts, secrets, and debugging, using real artifacts rather than abstract tutorials.

## Success criteria / completion metrics
- Local single-node k3s cluster running; services can be deployed, observed, and debugged with `kubectl`.
- Helm charts for at least two previously local services (for example `telemetry-hub` and `keycloak-setup`) with documented values, secrets handling, and zero-downtime rolling updates.
- Liveness/readiness probes demonstrated; induced failure is recovered by Kubernetes without manual intervention.
- CI builds images and runs `helm lint` and upgrade tests; no secrets in version control.
- Local Terraform (in `terraform-k3s`) is a follow-on; this project establishes the Kubernetes patterns first.

## Prerequisites and dependencies
- `go-http-server`, `telemetry-hub`, `keycloak-setup` locally runnable first.
- Docker.
- Helm 3.

## Tools, libraries, and runtime
- k3s.
- kubectl, Helm 3.
- Docker.
- Optional: Sealed Secrets or SOPS for local secrets.
- Local CI.

## Learning objectives (skills practiced)
- Kubernetes resources: Deployment, Service, ConfigMap, Secret, Ingress.
- Health probes, resource requests/limits, and rolling update behavior.
- Helm chart design: reusable values, templates, hooks, and `helm test`.
- Secrets and configuration: where secrets live, how Helm references them, and what NOT to commit.
- Debugging with `kubectl`: logs, describe, events, exec, port-forward.
- Local vs. production differences and when abstractions hide dangerous behavior.

## Architecture / design note
```
charts/
  telemetry-hub/
    Chart.yaml
    values.yaml
    templates/
  keycloak-setup/
    Chart.yaml
    values.yaml
    templates/
k3s-setup/
  README.md
  bootstrap.sh
Jenkinsfile
```
Charts wrap existing services; they should not require application code changes. Values should separate environment-specific config from chart defaults.

## Test strategy
- `helm lint` and `helm template` diff in CI.
- Helm test hooks for each chart when meaningful.
- Deployment smoke tests: service is reachable after rollout, probes pass, config is applied.
- Pod deletion/recreate test: confirms Deployment recreates the pod.
- Secret handling test: confirm no secrets in rendered manifests by CI diff.

## Documentation checklist
- `README.md` with cluster setup, Helm workflow, upgrade/rollback commands, and troubleshooting.
- Values documentation for each chart.
- Secrets handling policy and recovery from accidental secret commits.
- Debugging playbook: `kubectl` commands for common investigation steps.

## API contract
None at the Kubernetes layer; charts expose the application APIs unchanged.

## UI / status surfaces
Kubernetes Dashboard is optional; terminal `kubectl` is the primary interface to learn.

## Security boundaries to think about
- Run services with least-privilege RBAC where applicable.
- Do not commit secrets; explain what happens when a secret is in git history.
- NetworkPolicies are optional but useful to practice; document the chosen model.
- Ingress TLS and cert management are a follow-on; use self-signed or local certs deliberately.

## Profiling plan
Profile is not the focus. Resource utilization is observed via `kubectl top`; do not treat it as a precision measurement.

## How this project fits into the curriculum
Deploys the services built earlier. `terraform-k3s` follows by provisioning the infrastructure with code. `keycloak-setup` becomes a deployed service here.

## Suggested milestone walkthrough
1. **k3s local cluster.** Install and verify k3s; deploy a trivial service.
2. **Helm chart for telemetry-hub.** Wrap the existing service; deploy with zero-downtime rollout.
3. **Probes and failure recovery.** Add liveness/readiness; induce a failure and observe recovery.
4. **Secrets and ConfigMaps.** Handle secrets without committing them; document the policy.
5. **keycloak-setup chart.** Deploy Keycloak; configure OAuth-protected routing.
6. **CI + debugging.** CI builds images, runs `helm lint`, and performs an upgrade test. Practice `kubectl` debugging commands.

## Reference notes and resources
- k3s documentation.
- Helm documentation and chart best practices.
- Kubernetes documentation for core resources, probes, and rollouts.
- kubectl cheat sheet.
