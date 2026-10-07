# Terraform on k3s

## What this project exists to solve
Learn infrastructure-as-code by modeling reproducible local infrastructure and local k3s, using Terraform where the chosen provider supports it and acknowledging limits explicitly. The goal is to understand what Terraform owns, what Helm owns, and why state and secrets require special care.

## Success criteria / completion metrics
- Terraform configuration that provisions reproducible local infrastructure (for example, a local VM or local k3s via a supported provider/approach).
- Idempotent `terraform plan`/`apply` behavior documented for clean state, partial state, and drift scenarios.
- Secrets handled safely: not stored in state or version control, with a documented rotation/recovery note.
- Helm-managed Kubernetes resources are separate from Terraform-managed infrastructure; the boundary is explicitly documented.
- If provider limits prevent full k3s provisioning via Terraform alone, the chosen approach (for example, Terraform plus a bootstrap script) is documented with rationale.

## Prerequisites and dependencies
- `k3s-helm` for Kubernetes and Helm understanding.
- Local libvirt or equivalent provider if available; this project respects provider support rather than forcing a cloud account.

## Tools, libraries, and runtime
- Terraform or OpenTofu.
- A local provider supported on the host (for example, libvirt, Proxmox, or a local VM provider); otherwise a documented local-k3s path.
- kubectl and Helm for follow-on resource management.
- Local CI to validate Terraform formatting and plan stability.

## Learning objectives (skills practiced)
- Terraform workflow: init, plan, apply, state, drift detection, and destroy.
- Provider selection and limits: what Terraform can manage and where it delegates to other tools.
- Sensitive values: why state contains secrets by default, how to mitigate, and what to do when a secret leaks.
- Immutable infrastructure vs. mutable configuration.
- Separation of infrastructure provisioning and application deployment (Terraform vs. Helm).
- Review-first workflow and plan-output review as a habit.

## Architecture / design note
```
terraform/
  main.tf
  variables.tf
  outputs.tf
  providers.tf
  README.md
scripts/
  bootstrap.sh               # if needed for steps Terraform cannot express
```

Terraform owns the infrastructure boundary: VM/network/k3s host. Helm charts from `k3s-helm` own application deployment on top. Document this explicitly so later work does not conflate layers.

## Test strategy
- `terraform fmt -check` and `terraform validate` in CI.
- `terraform plan` is reviewed; no `-auto-approve` in learning workflows.
- Provisioning test: fresh state provisions the same environment reproducibly.
- Drift test: manual change to a resource triggers a plan diff; restore via apply or manual decision.

## Documentation checklist
- `README.md` with provider choice, prerequisites, `terraform init/plan/apply` workflow, and destroy instructions.
- Provider support notes: which resources are managed by Terraform, which by Helm or scripts, and why.
- Secrets handling policy and state protection guidance.
- Known limits and how they were worked around.

## API contract
None. Terraform outputs are infrastructure identifiers (IPs, hostnames, kubeconfig).

## UI / status surfaces
None. Outputs are consumed by kubectl and Helm.

## Security boundaries to think about
- Terraform state files can contain secrets; protect state storage and never commit it.
- Provider credentials must not be embedded; use environment variables or local credential files out of source control.
- Understand the difference between a resource being "created" and being "secure by default."
- Kubernetes resources still need least-privilege RBAC and secrets handling even when deployed via Terraform.

## Profiling plan
Profile is not the focus. Measure plan/apply time and compare across changes if it becomes a meaningful question; do not optimize Terraform runs reflexively.

## How this project fits into the curriculum
Provides reproducible infrastructure for the projects deployed in `k3s-helm`. Treats infrastructure as code with the same review/test discipline as application code.

## Suggested milestone walkthrough
1. **Provider selection.** Confirm a supported local provider; document what Terraform can and cannot do with it.
2. **Infrastructure.** Provision a VM or local k3s host; capture outputs and SSH/kubeconfig paths.
3. **Secrets.** Configure sensitive values safely; document state protections.
4. **Integration.** Chain Terraform outputs into Helm deployments; document what each tool owns.
5. **Review workflow.** Add CI checks for formatting, validation, and plan output review.

## Reference notes and resources
- Terraform or OpenTofu documentation.
- Provider documentation for the chosen local provider.
- State encryption and sensitive value guidance from HashiCorp.
