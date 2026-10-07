# cicd-local
**Goal:** Run a fully local push → build → test → deploy CI/CD loop using Jenkins (or Gitea Actions) in Docker, a local image registry, and k3s — no cloud account required.

**Scope:** Jenkins or Gitea Actions running in Docker, Jenkinsfile (or workflow YAML) for `go-http-server`, pipeline stages (checkout → lint → test → build image → push to local registry → deploy to k3s), local `registry:2` Docker registry, triggered builds on local git push.

**Out of scope:** Cloud CI providers (GitHub Actions hosted runners, CircleCI, etc.), multi-node Jenkins clusters, production secrets management, CD to any remote environment.

**Learning focus:** Pipeline-as-code concepts, agents/nodes, stage gates, artifact archiving, triggered builds, credential stores, CI agent permission scoping.

**Depends on:** `go-http-server`, `k3s-helm`

## Milestones
- [ ] Milestone 1 — Run Jenkins (or Gitea Actions) locally in Docker; authenticate and create a seed job that prints environment info
- [ ] Milestone 2 — Write a Jenkinsfile for `go-http-server`: lint, test, build image, push to local `registry:2`
- [ ] Milestone 3 — Add a deployment stage: `kubectl apply` or `helm upgrade` to local k3s from inside the pipeline
- [ ] Milestone 4 — Trigger a build from a local `git push`; observe and verify the full end-to-end loop
- [ ] Milestone 5 — Document pipeline-as-code decisions, common failure modes, and a runbook for adding a new project to CI
