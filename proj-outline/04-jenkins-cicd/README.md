# 04 — Jenkins: CI/CD from Source to Cluster

**Folder:** `04-jenkins-cicd/`
**Milestone:** M6 (CI), M7 (CD)

---

## Teach first: what CI/CD really means

### The two halves people conflate

- **CI — Continuous Integration.** Every commit is automatically built and tested, so integration problems are caught in minutes, not at release. The output is a *verified artifact*.
- **CD — Continuous Delivery/Deployment.** That verified artifact is automatically deployed to an environment. *Delivery* = ready to deploy behind an approval. *Deployment* = deployed with no human in the loop.

> **Senior lens** — the point of CI is **fast feedback**, and the point of CD is **small, reversible change**. The value isn't the automation itself; it's that changes get small enough to reason about and roll back. A pipeline that takes 40 minutes defeats CI's purpose. A pipeline with no rollback path makes CD dangerous. Measure and optimize both.

### Pipeline as code

Jenkins's original sin was clicking buttons to define jobs — unversioned, unreviewable, unreproducible. The modern approach is **pipeline-as-code**: a `Jenkinsfile` in the repo, reviewed like any code.

There are two syntaxes:
- **Declarative** (`pipeline { stages { ... } }`) — structured, opinionated, easier to read. **Use this.**
- **Scripted** (`node { ... }`) — full Groovy, flexible, harder to reason about. Escape hatch only.

### The stages of a real pipeline

```
Checkout → Build → Unit Test → Static Analysis → Build Image → Scan → Push → Deploy → Smoke Test → Promote
```

Each stage either **succeeds** (proceed) or **fails** (stop, alert). The artifact only moves forward if every gate passes.

---

## Why Jenkins (and not just GitHub Actions)?

Since you specifically want to **own the whole stack**, Jenkins is the right pick here — it's the classic self-hosted CI/CD server, deeply configurable, and running it yourself teaches you the agent model, the plugin ecosystem, credentials management, and JCasC. You also learn its *warts* — the plugin sprawl, the upgrade pain, the resource hunger — which is exactly the kind of operational knowledge you want.

> **Tradeoff — Jenkins vs. GitHub Actions/GitLab CI/ArgoCD.** Managed CI (Actions, GitLab) removes the operational burden but hides the machinery. Jenkins makes you own the controller, the agents, the credentials store, and the plugin lifecycle — more work, more learning, more failure modes. For *this* project (own everything) Jenkins is the right call. Note for your career: modern shops increasingly prefer GitLab CI or ArgoCD + GitHub Actions; Jenkins is still everywhere in enterprises, so the skills transfer.

---

## The Jenkins architecture

| Component | Role |
|---|---|
| **Controller** | The server. Holds job config, credentials, schedules builds. Should NOT run builds. |
| **Agent** | Where builds actually execute. Ephemeral agents (Kubernetes pods) are the modern pattern. |
| **Executor** | A slot on an agent. Limits concurrent builds per agent. |
| **Workspace** | The checkout dir on an agent. Ephemeral if the agent is. |
| **Plugin** | Extends Jenkins. The ecosystem is huge — and a liability. |

> **Senior lens — the controller must never run builds.** On the controller, a heavy build competes with the UI, the scheduler, and the credential store, and one bad build can hang the whole controller. The mature pattern is **Kubernetes agents**: Jenkins spins up a pod per build, runs the stages, then destroys the pod. This gives isolation, clean workspaces, and elastic capacity. This is exactly what you'll set up, and it links Jenkins directly to your cluster (doc 02).

---

## JCasC: Jenkins Configuration as Code

Clicking through the Jenkins UI to configure it violates everything this project stands for (unversioned, unreviewable, unreproducible). **JCasC** lets you define the entire Jenkins config in YAML, version it in Git, and apply it on startup.

```yaml
jenkins:
  systemMessage: "Outline platform CI/CD"
  numExecutors: 0          # controller runs nothing
  clouds:
    - kubernetes:
        name: k8s
        serverUrl: https://kubernetes.default
        namespace: cicd
        templates:
          - name: builder
            label: builder
            containers:
              - name: jnlp
              - name: docker
              - name: kubectl
credentials:
  system:
    domainCredentials:
      - credentials:
          - usernamePassword:
              id: harbor-creds
              username: jenkins
              password: ${HARBOR_PASSWORD}
```

> **Senior lens** — JCasC is what turns Jenkins from a pet into cattle. If the controller dies, you recreate it and it configures itself from Git. `${HARBOR_PASSWORD}` comes from an env var/sealed secret, not committed. **Without JCasC, Jenkins is a snowflake you're afraid to touch — the opposite of what you want.**

---

## Credentials: how Jenkins holds secrets

Jenkins has a **Credentials** store for:
- **Username/password** — Harbor login, registry auth
- **SSH keys** — cloning private repos, SSH-ing to nodes
- **Secret text** — API tokens (Slack, cloud)
- **Secret file** — kubeconfigs, service account JSON

Credentials are referenced by **ID** in pipelines — the secret itself never appears in the Jenkinsfile:

```
withCredentials([usernamePassword(
  credentialsId: 'harbor-creds',
  usernameVariable: 'REG_USER',
  passwordVariable: 'REG_PASS'
)]) {
  sh 'echo "$REG_PASS" | docker login harbor.lab.example -u "$REG_USER" --password-stdin'
}
```

> **Failure mode** — `echo $PASS` in a pipeline prints the secret to the build log. Jenkins *masks* known secrets in logs, but masking is best-effort (base64, substrings, and transformations can slip through). Rule: **never echo credentials; always pipe them.** And to the kubeconfig point: the CD pipeline's kubeconfig should belong to a **scoped service account** (doc 14), not a cluster-admin.

---

## The two pipelines you'll build

### CI pipeline (on every push)

```
1. Checkout
2. Install deps + lint (TypeScript)
3. Run unit tests
4. Static analysis (type-check)
5. Build the Docker image (multi-stage)
6. Scan the image with Trivy (via Harbor on push, or locally)
7. Tag: <git-sha> + branch name
8. Push to Harbor
9. (Optionally) run integration tests against ephemeral Postgres/Redis
```

Key properties:
- **Fast.** Fail early — lint and unit tests before the expensive image build.
- **Deterministic.** Pin base images by digest; use `npm ci` (not `npm install`).
- **Tagged immutably.** `outline:<git-sha>` — never `:latest` for anything deployable.

> **Senior lens — never deploy `:latest`.** If your deployment references `:latest`, you cannot answer "what code is running right now?" and rollback becomes guesswork. Tag by **git SHA** (or a build number). Immutable tags are the foundation of reproducible deploys and clean rollbacks. `:latest` is acceptable only as a *pointer* for humans, never as a deploy target.

### CD pipeline (on tag, or gated on approval)

```
1. Checkout (the repo, at the tag)
2. Determine image tag (git-sha)
3. helm diff upgrade outline ...        # show what changes
4. APPROVAL GATE (input step)           # human says go
5. helm upgrade --install --atomic --wait --timeout 5m
6. Run DB migrations (if needed)
7. Smoke test (curl health endpoint)
8. On failure: automatic rollback (--atomic) + alert
```

> **Senior lens** — the approval gate is where **continuous delivery** lives (vs. deployment). For a homelab, gate on approval so you always see the diff and the plan before it ships. The `--atomic` flag means a failed deploy auto-rolls-back, so the "on failure" path is handled by Helm, not by your pipeline logic. Fewer moving parts = fewer 3am bugs.

---

## Pipeline structure (declarative) — the shape

```
pipeline {
  agent { label 'builder' }              // runs on a k8s pod (doc 02)
  environment {
    REGISTRY = 'harbor.lab.example'
    IMAGE    = "${REGISTRY}/outline"
    TAG      = "${env.GIT_COMMIT.take(8)}"
  }
  options {
    timeout(time: 30, unit: 'MINUTES')   // never let a build hang forever
    buildDiscarder(logRotator(numToKeepStr: '30'))  // bound history
    disableConcurrentBuilds()            // avoid racing deploys
  }
  stages {
    stage('Lint')     { ... }
    stage('Test')     { ... }
    stage('Build')    { ... }
    stage('Scan')     { ... }
    stage('Push')     { ... }
    stage('Deploy')   { when { tag "v*" } ... }   // only on tagged releases
  }
  post {
    failure { notify('failed') }
    always  { cleanWs() }                // don't leak workspaces
  }
}
```

> **Threshold — pipeline timeout.** Always set one. A hung build (waiting on a registry, a network call) otherwise consumes an executor forever. For this project, 30 minutes is generous. Also set `buildDiscarder` — unbounded build history fills the controller's disk.

---

## Webhooks: how builds start

- **Poll SCM** — Jenkins checks Git on a schedule. Simple, laggy, wasteful. Avoid.
- **Webhooks** — Git (or a generic webhook) notifies Jenkins on push. Immediate, efficient.
- **Multibranch pipeline** — Jenkins auto-discovers branches and PRs and runs the right pipeline per branch. This is the modern default.

> **Senior lens** — **multibranch pipelines** are how you get PR builds (test before merge) and branch builds (test after merge) for free. Combined with webhooks, every push gets a build within seconds. This is the CI heart of the project.

---

## Scaling agents

The Kubernetes agent model gives you near-infinite elasticity: each build gets a fresh pod. Benefits:

- **Isolation** — one build can't poison another's workspace.
- **Clean state** — no stale `node_modules`, no leftover Docker layers.
- **Elastic** — 10 concurrent builds → 10 pods → 0 when idle.

> **Tradeoff — ephemeral vs. persistent agents.** Ephemeral pods are clean and elastic but pay startup cost per build (pull image, provision). Persistent agents cache and are faster but drift and leak. **Ephemeral is the right default** for this project; use persistent agents (or a cache) only where build time demands it.

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| Controller running builds | Never — set `numExecutors: 0` |
| Agent model | Kubernetes ephemeral pods for isolation + elasticity |
| Config | JCasC from Git; never click-configure |
| Image tags | Git SHA, immutable; never `:latest` for deploys |
| Timeout | Always set; 30m is generous for this project |
| Build history | Bound with `buildDiscarder`; else disk fills |
| Deploy flags | `helm upgrade --install --atomic --wait` |
| Approval | Gate CD for a homelab; watch the diff before shipping |
| Secrets | Credentials store + `withCredentials`; never echo |

---

## Failure modes you must deliberately cause

1. **Fail a test** → pipeline stops before the image build; verify fail-fast ordering.
2. **Push a bad image** → `--atomic` rolls back; observe the rollback in `helm history`.
3. **Hang a build** → confirm the timeout kills it and frees the executor.
4. **Run two deploys concurrently** → see why `disableConcurrentBuilds()` matters.
5. **Echo a credential** → see the masking (and understand its limits).
6. **Deploy `:latest`** → try to roll back; feel the pain; never do it again.
7. **Delete the controller pod** → with JCasC, it should rebuild its config on restart.

---

## Exit criteria for M6 & M7

- [ ] Jenkins runs as a Helm release with `numExecutors: 0` and JCasC from Git
- [ ] Kubernetes ephemeral agents spin up per build
- [ ] CI pipeline builds Outline, scans it, and pushes to Harbor on every push
- [ ] CD pipeline shows a `helm diff`, gates on approval, and deploys with `--atomic --wait`
- [ ] A failed deploy auto-rolls-back
- [ ] A commit in Git results in a running deployment with no manual steps (outside approval)

Next: `05-artifact-repository` — where the artifacts live.
