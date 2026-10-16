# 01 — Terraform: Infrastructure as Code

**Folder:** `01-terraform-infra/`
**Milestone:** M1 — Infra

---

## Teach first: what Terraform is, and the idea behind it

### The problem Terraform solves

Before infrastructure-as-code (IaC), provisioning infrastructure meant clicks. You logged into a hypervisor or a cloud console, clicked "create VM," typed some settings, waited, then SSH'd in and configured things by hand. This had three fatal properties:

1. **It wasn't reproducible.** Two "identical" servers drifted apart over weeks.
2. **It wasn't reviewable.** Nobody could see what changed, or why.
3. **It wasn't recoverable.** If the server died, nobody knew the exact steps to rebuild it.

IaC treats infrastructure the same way we treat application code: it lives in Git, it's reviewed, it's versioned, and it can be rebuilt from scratch.

### What Terraform specifically is

Terraform is a **declarative** IaC tool. You describe the **desired end state** — "there should be three VMs with these specs, this network, this firewall rule" — and Terraform figures out the **actions** needed to get there.

This is the key mental shift. You do not write "create VM, then attach disk, then open port." You write:

> *This is what the world should look like.*

Terraform then:
1. **Reads** the current state of the world (from its state file + the provider APIs).
2. **Diffs** desired vs. actual.
3. **Plans** the minimal set of actions.
4. **Applies** them, in the correct dependency order.

### The three core concepts

- **Provider** — a plugin that knows how to talk to some system (Proxmox, AWS, Kubernetes, Cloudflare DNS). Each provider exposes *resources* and *data sources*.
- **Resource** — a thing Terraform manages (`proxmox_vm_qemu`, `cloudflare_record`). Its lifecycle is owned by Terraform.
- **State** — Terraform's record of what it created. This is critical, and the #1 source of beginner pain, so we'll spend real time on it.

### Why declarative beats imperative here

With an imperative script (`run these commands`), running it twice creates two of everything. With Terraform, running it twice creates **zero** — because the world already matches the desired state. This property is called **idempotency**, and it's the reason Terraform can be run safely on a schedule, in CI, or by anyone on the team.

---

## Why this fits *this* project

Your homelab is the foundation everything else sits on. If the nodes, networking, and cluster bootstrap are hand-made, then every layer above them (Kubernetes, Helm, Jenkins) is built on sand — because you can't prove the base is correct, and you can't rebuild it.

Terraform gives you three things this project specifically needs:

1. **A rebuildable base.** The whole point of the project (see `00-learning-path`, "How to know you're done") is that you can destroy everything and rebuild from Git. That's only possible if the infra is code.
2. **A place to enforce networking and firewall policy as code.** Your homelab has a flat network by default; Terraform lets you define the segmentation between "nodes," "management," and "load balancer" explicitly.
3. **A bridge to the cluster.** Terraform's Kubernetes provider lets you install cluster add-ons (ingress, cert-manager, monitoring) as part of the same apply that provisions the nodes — so "bare metal → working cluster" is one command.

---

## The components you'll actually write

### 1. Node provisioning (the Proxmox path)

For a homelab, the **Proxmox provider** is the natural choice. You define VMs declaratively: CPU, memory, disk, network bridge, cloud-init userdata.

```
variable "node_count"    { default = 3 }
variable "node_memory_gb" { default = 8 }
variable "node_cores"     { default = 4 }
```

Three nodes is the floor for anything interesting, because it's the minimum for a **quorum** in etcd (the cluster's brain). Two nodes is the worst possible number — you get neither high availability nor simplicity. This is a classic **threshold**:

> **Threshold** — etcd needs an odd number of members to maintain quorum. 1 is fragile, 2 is *worse* than 1 (a single failure breaks quorum and you lose the ability to make any changes), 3 tolerates 1 failure, 5 tolerates 2. For a homelab, **3 is the minimum you should run** if you want the cluster to survive a node death.

### 2. Cluster bootstrap (k3s / RKE2)

Options:
- **k3s** — lightweight, single binary, SQLite by default (but you'll switch to external etcd or embedded etcd for HA). Great for homelabs.
- **RKE2** — security-hardened k3s, closer to upstream k8s, default etcd. Heavier but more "production-like."
- **kubeadm** — upstream, most "from scratch." Most educational, most tedious.

> **Tradeoff** — k3s is fast to stand up and easy to reason about, but it deviates from upstream k8s in some defaults, so some things you learn won't transfer 1:1. kubeadm teaches you the *real* components (kube-apiserver, kube-controller-manager, kube-scheduler, etcd) as separate processes you configure yourself. **For learning, kubeadm is the most honest.** For getting to the interesting layers (Jenkins, observability) fast, k3s is the pragmatic pick. My recommendation: **start with k3s to reach M2 quickly, then re-do it with kubeadm once you're comfortable** — the second pass is where the control-plane knowledge sticks.

### 3. Networking and DNS

- A stable internal IP per node.
- DNS records (via Cloudflare provider or local DNS) for services: `outline.lab.example`, `harbor.lab.example`, `grafana.lab.example`.
- If you expose services externally, a load balancer or a DNS-01 ACME challenge for cert-manager (so you get real TLS without exposing port 80).

### 4. Cluster add-ons (Terraform Kubernetes/Helm provider)

Install as part of the same apply:
- `ingress-nginx` — the entry point for HTTP(S) traffic
- `cert-manager` — automatic TLS certificate issuance and renewal
- `kube-prometheus-stack` — Prometheus + Grafana + exporters (detail in doc 11)
- `cloudnative-pg` — the Postgres operator (detail in doc 06)

---

## State management — the part beginners get wrong

Terraform state is a JSON file that maps your `.tf` resources to real-world objects. If you lose it, Terraform thinks nothing exists and will try to create duplicates; if two people run it against the same state simultaneously, you get corruption.

### Rules that matter

> **Failure mode** — **local state**. By default, Terraform writes `terraform.tfstate` to your working directory. This means no locking, no sharing, and a high risk of committing it to Git (which can leak secrets). **Never use local state for anything you care about.**

> **Fix** — **remote backend with locking**. Configure a backend (MinIO/S3-compatible, Postgres, or Terraform Cloud) so state lives centrally and holds a lock during apply. For this project, use MinIO (which you'll deploy in doc 08) or a Postgres backend — both reinforce components you're already learning.

> **Failure mode** — **state drift**. Someone edits a resource by hand (e.g. resizes a VM in the Proxmox UI). Terraform's state no longer matches reality. On next apply, Terraform may try to "fix" the drift by reverting your manual change — which could be fine, or could destroy work.

> **Detection** — run `terraform plan` on a schedule (in CI). If the plan isn't empty, you have drift. An empty plan is the health check of an IaC repo.

### Secrets in state

Terraform records secrets (passwords, tokens) **in plaintext in the state file**. This is a fundamental property, not a bug.

> **Senior lens** — any value a provider returns that's sensitive lands in state. So the backend must be encrypted at rest and access-controlled. Rotating a secret means it's still in old state snapshots — you must scrub them. For this project, treat the state backend as a **secrets store** and secure it accordingly.

---

## The workflow you'll live in

```
terraform init      # download providers, configure backend
terraform validate  # syntax + internal consistency
terraform plan      # show what WOULD change (the review artifact)
terraform apply     # make it so
terraform destroy   # tear it all down (use deliberately)
```

**`plan` is the most important command.** In a team, the plan output is what gets reviewed in a PR. A plan that says "0 to add, 0 to change, 1 to destroy" on a database resource should stop everyone cold.

---

## Directory structure that scales

```
01-terraform-infra/
├── modules/
│   ├── node/            # one VM definition, parameterized
│   ├── cluster/         # k8s bootstrap (k3s/kubeadm)
│   └── addons/          # ingress, cert-manager, monitoring
├── environments/
│   ├── lab/             # the homelab environment
│   │   ├── main.tf
│   │   ├── backend.tf   # remote state config
│   │   └── terraform.tfvars
└── README.md (this file)
```

**Modules** are reusable, parameterized bundles of resources. **Environments** wire modules together with concrete values. This split is what lets you have a `lab` and a `prod` that differ only in variables.

> **Senior lens** — resist the urge to make one giant `main.tf`. Modules force you to define clear inputs (variables) and outputs, which documents the interface between layers. The test: *could a colleague use this module without reading its implementation?*

---

## Thresholds and tradeoffs summary

| Decision | Option A | Option B | Guidance |
|---|---|---|---|
| Cluster distro | k3s | kubeadm | k3s to move fast; kubeadm to actually learn the control plane |
| Node count | 2 | 3 | Never 2. 3 is the HA floor (etcd quorum) |
| State backend | local | remote + lock | Remote, always, once beyond a toy |
| K8s distro HA | embedded etcd | external etcd | Embedded is fine for 3 nodes; external for 5+ or multi-DC |
| Add-on management | Terraform Helm provider | ArgoCD/Flux | Terraform for "bootstrap"; GitOps for "steady state" (see below) |

> **Tradeoff — Terraform vs. GitOps (ArgoCD/Flux) for cluster resources.** Terraform is excellent at *bootstrapping* (bringing a cluster into existence) but awkward at *continuous reconciliation* (a running app should self-heal to its declared state). GitOps tools are built exactly for the latter. The mature pattern is **Terraform for infra + bootstrap, GitOps for workloads**. Note this now; you'll appreciate it when you reach Jenkins CD.

---

## Failure modes you must deliberately cause

1. **Corrupt/lose the state file** (in a throwaway env) → watch Terraform try to recreate everything. Now you understand why backups of state matter.
2. **Hand-edit a resource** out-of-band → run `plan`, see the drift, decide whether to accept it (`import`) or revert.
3. **Two concurrent applies** (with locking off) → see the corruption. Then turn locking on.
4. **Destroy and rebuild** the whole environment from Git → time it. This is your M1 exit criterion.

---

## Senior lens: what separates a good Terraform repo from a bad one

- **It's boring.** No clever `for_each` gymnastics. Readable > compact.
- **Plans are small.** A PR that plans 40 changes is a PR nobody can review — split it.
- **State is remote, locked, encrypted, versioned.**
- **Secrets never live in `.tf` or `.tfvars` committed to Git.** They come from a secret manager or `TF_VAR_*` env injection in CI.
- **Outputs are the interface.** The `cluster` module outputs a kubeconfig; the `addons` module consumes it. Explicit contracts, not globals.
- **`terraform destroy` is not scary.** If tearing down makes you nervous, your env has out-of-band state — a smell.

---

## Exit criteria for M1

- [ ] 3 nodes provisioned entirely by Terraform
- [ ] k3s (or kubeadm) cluster bootstrapped, `kubectl get nodes` shows 3 Ready
- [ ] Remote state backend with locking configured
- [ ] `terraform plan` is empty on a clean run (no drift)
- [ ] `terraform destroy` → `terraform apply` rebuilds everything from Git
- [ ] ingress-nginx + cert-manager installed via Terraform

Next: `02-kubernetes-core` — what actually happens inside that cluster you just built.
