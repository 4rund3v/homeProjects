# Terraform on k3s

**Goal:** Learn infrastructure-as-code by modeling reproducible local infrastructure, local k3s, and follow-on Helm-managed resources.

**Scope:** Local virtual-machine and k3s provisioning where the provider supports it, SSH/connectivity, sensitive values, immutable infrastructure principles, and Helm integration. Configure Kubernetes resources through Terraform only where it adds clarity; otherwise prefer Helm.

**Out of scope:** Multi-cloud patterns and managed cloud Kubernetes. Those follow if the learner later introduces a supported environment.

**Learning focus:** What Terraform owns vs. what Helm owns, state drift, sensitive data handling, review-first workflow, and when a smaller tool is better.

**Depends on:** `k3s-helm` (for Kubernetes concepts), local libvirt/virtualization available on the host.

## Milestones
- [ ] Provision a single local VM or provision the local k3s server using Terraform with documented inputs and outputs.
- [ ] Store and pass sensitive values safely; explain the difference between secrets in Terraform state and in Kubernetes.
- [ ] Integrate with Helm charts for already-local projects; document idempotent `terraform apply` behavior.
- [ ] Add a plan-review workflow and compact change log; treat Terraform code as read-only infrastructure and the local state file as protected.

## Tools
- Terraform or OpenTofu, a local virtualization provider if available (e.g., libvirt) or a local-k3s path, kubectl, Helm.
