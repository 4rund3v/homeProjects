# cicd-local

## What this project exists to solve
Most developers use CI/CD through a hosted service and never see what actually runs behind the curtain.
This project forces everything local — the CI server, the image registry, the Kubernetes cluster — so the learner can inspect, break, and fix every layer of the pipeline without cloud abstractions.
It closes the loop on the earlier curriculum projects by wiring `go-http-server` and the `k3s-helm` cluster into an automated delivery chain.
The result is a reproducible, offline-capable pipeline that mirrors real GitOps workflows at a small scale.

## Success criteria / completion metrics
- Jenkins (or Gitea Actions) starts reliably from a `docker compose up` and survives a restart without losing configuration
- A single `git push` to the local repo triggers an automated pipeline run with no manual steps
- Pipeline stages are discrete and individually re-runnable: checkout, lint, test, build image, push to registry, deploy
- The `go-http-server` image appears in the local `registry:2` after a successful build
- A new revision of `go-http-server` is reachable in k3s within 2 minutes of the triggering push
- No secrets (passwords, tokens) appear anywhere in the Jenkinsfile or workflow YAML; all are injected from the credential store
- A written runbook exists explaining how to onboard a second project into the pipeline

## Prerequisites and dependencies
- `go-http-server` project completed: produces a buildable Docker image and has passing tests
- `k3s-helm` project completed: a running local k3s cluster reachable via `kubectl`
- Docker and Docker Compose installed on the host
- Familiarity with Dockerfile authoring and basic Helm chart structure

## Tools, libraries, and runtime
- **CI server:** Jenkins LTS (`jenkins/jenkins:lts-jdk21`) OR Gitea + Gitea Actions (`gitea/gitea:latest`) — learner chooses one
- **Agent/runner:** Jenkins inbound-agent Docker image OR `act_runner` for Gitea Actions
- **Local registry:** `registry:2` (Docker Distribution) exposed on `localhost:5000`
- **Orchestration:** `docker compose` to bring up the CI stack
- **Build tools inside pipeline:** `go`, `golangci-lint`, `docker` CLI (Docker-in-Docker or socket mount), `kubectl`, `helm`
- **Git hosting:** local Gitea instance (if using Gitea Actions) or bare git repo with webhook (if Jenkins)
- **k3s:** from `k3s-helm` project; reachable via host `~/.kube/config`

## Learning objectives (skills practiced)
- Writing pipeline-as-code: declarative Jenkinsfile stages or Gitea Actions workflow YAML steps
- Configuring agents/runners: understanding where each stage command actually executes
- Stage gates: failing fast on lint/test before spending time on image build
- Storing and injecting credentials via Jenkins Credential Store or Gitea secrets — never in source
- Pushing and pulling images from a local (insecure) Docker registry, including daemon `insecure-registries` config
- Triggering builds via webhooks from a local git push
- Archiving build artifacts and test reports within the pipeline
- Scoping CI agent permissions: what the pipeline user can and cannot do in k3s (RBAC)

## Architecture / design note
```
host machine
├── docker compose stack (cicd-local/)
│   ├── jenkins (or gitea + act_runner)
│   ├── registry:2  → localhost:5000
│   └── (optional) gitea  → localhost:3000
├── ~/.kube/config  → k3s cluster from k3s-helm project
└── local git repos
    └── go-http-server/  ← push here triggers the pipeline
```
Key decisions to make explicitly:
- **Docker socket vs. DinD:** mounting `/var/run/docker.sock` into the agent is simpler but gives the agent root on the host; DinD is isolated but heavier. Document whichever is chosen and why.
- **Insecure registry:** k3s nodes and the Docker daemon on the host must both be configured to trust `localhost:5000` without TLS. Document the config files changed.
- **Kubeconfig access:** pass a scoped `KUBECONFIG` into the pipeline via the credential store; do not mount the full admin config.

## Test strategy
- **Smoke test (Milestone 1):** seed job runs and prints `JAVA_HOME` / `GOPATH` / agent hostname; build is GREEN
- **Unit test stage (Milestone 2):** pipeline invokes `go test ./...` for `go-http-server`; a deliberately broken test must turn the stage RED and halt the pipeline before image build
- **Image push verification (Milestone 2):** after a successful run, `curl localhost:5000/v2/go-http-server/tags/list` must return the new tag
- **Deploy verification (Milestone 3):** after the deploy stage, `kubectl rollout status deployment/go-http-server` must report `successfully rolled out`; `curl` the service endpoint and assert HTTP 200
- **End-to-end trigger test (Milestone 4):** make a visible code change, push, wait, confirm the new version is live — without any manual pipeline trigger

## Documentation checklist
- `README.md` — quick-start: how to bring the stack up and tear it down
- `Project.md` — this file
- `docker-compose.yml` — inline comments on every non-obvious setting
- `Jenkinsfile` (or `.gitea/workflows/ci.yml`) — comment each stage explaining *why*, not just *what*
- `docs/runbook-add-project.md` — step-by-step guide to onboarding a second project
- `docs/failure-modes.md` — common pipeline failures and how to diagnose them (registry unreachable, kubeconfig permission denied, lint timeout, etc.)

## API contract
No HTTP API. The pipeline is triggered by a git webhook POST to the CI server. Interaction is via the Jenkins/Gitea web UI and `git push`.

## UI / status surfaces
- Jenkins Blue Ocean or classic UI (port 8080) — build history, stage view, console log
- Gitea web UI (port 3000, if chosen) — Actions tab shows workflow runs
- `kubectl get pods` and `kubectl rollout status` — deployment state
- Local registry `/v2/<name>/tags/list` endpoint — image inventory

## Security boundaries to think about
- **Docker socket mount:** grants the CI agent effective root on the host; document this risk and consider DinD as mitigation
- **Jenkins Credential Store / Gitea secrets:** registry username/password and the scoped kubeconfig must be stored here, never in the Jenkinsfile or workflow YAML
- **k3s RBAC:** create a dedicated `ServiceAccount` with only the permissions the pipeline needs (`get`, `patch` on `deployments` in one namespace); bind it with a `RoleBinding`, not `ClusterRoleBinding`
- **Registry TLS:** the registry runs over plain HTTP on localhost; explicitly document why this is acceptable only for a local learning environment and what would change in production
- **Webhook secrets:** if using Jenkins webhooks, set a webhook secret token so only the local git server can trigger builds

## Profiling plan
Profile only if a performance question arises. If pipeline duration exceeds 5 minutes for a trivial change, investigate layer caching in Docker build and Go module caching between runs.

## How this project fits into the curriculum
`cicd-local` sits at Phase 6, project 22. It depends on `go-http-server` (the application being delivered) and `k3s-helm` (the deployment target). It is the first project that connects all earlier work into an automated loop and establishes the pattern used by any subsequent project that needs CI. Projects added later can follow the `docs/runbook-add-project.md` to plug into the same local pipeline.

## Suggested milestone walkthrough
1. Write a `docker-compose.yml` that starts Jenkins (or Gitea + act_runner) and `registry:2`; verify all containers are healthy
2. Log into the CI UI, unlock Jenkins / set up Gitea admin, and create a minimal seed job that echoes environment variables; confirm GREEN build
3. Configure the local git remote (or Gitea repo) for `go-http-server` and set up a webhook pointing to the CI server
4. Write the Jenkinsfile (or workflow YAML) with a `lint` stage using `golangci-lint` and a `test` stage using `go test`; push and confirm both stages run
5. Add a `build` stage that runs `docker build` and a `push` stage that tags and pushes to `localhost:5000`; verify the image appears in the registry API
6. Add a `deploy` stage that calls `helm upgrade --install` (or `kubectl apply`) using a credential-injected kubeconfig; verify rollout in k3s
7. Make a small visible change to `go-http-server`, push, and watch the full pipeline run end-to-end without manual intervention
8. Write `docs/failure-modes.md` and `docs/runbook-add-project.md`; update `README.md` with the quick-start commands

## Reference notes and resources
- [Jenkins Declarative Pipeline syntax](https://www.jenkins.io/doc/book/pipeline/syntax/)
- [Gitea Actions documentation](https://docs.gitea.com/usage/actions/overview)
- [Docker Distribution (registry:2) API](https://distribution.github.io/distribution/spec/api/)
- [Docker-in-Docker vs. socket mount trade-offs](https://jpetazzo.github.io/2015/09/03/do-not-use-docker-in-docker-for-ci/)
- [k3s private registry configuration](https://docs.k3s.io/installation/private-registry)
- [Kubernetes RBAC — least-privilege service accounts](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [golangci-lint](https://golangci-lint.run/)
