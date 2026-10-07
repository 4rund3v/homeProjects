# homer-dashboard

## What this project exists to solve
As the curriculum grows to 19+ runnable projects, navigating between them becomes friction. Homer provides a single browser tab that surfaces every project's documentation, live URL, and health status without requiring a custom application. The goal is to practice infrastructure-as-config discipline — the dashboard's state is fully described by a version-controlled `config.yml` — while also giving a concrete home base for the workspace.

## Success criteria / completion metrics
- Homer runs locally via `docker compose up` and is reachable at `http://localhost:8080`
- `config.yml` is committed to version control and is the sole source of truth for the dashboard layout
- All 19 curriculum projects appear, each with a label, subtitle, and link to its documentation
- Every project that exposes a health or UI endpoint has a status ping configured
- `config.yml` contains no secrets, tokens, or credentials
- A `CONTRIBUTING.md`-style section explains how to add a new project entry in under 5 minutes

## Prerequisites and dependencies
- Docker and Docker Compose installed and working locally
- Basic familiarity with YAML syntax
- No prior Homer experience required — reading the Homer README is part of Milestone 1

## Tools, libraries, and runtime
- [Homer](https://github.com/bastienwirtz/homer) — `ghcr.io/bastienwirtz/homer:latest`
- Docker Compose v2
- A browser for visual verification
- No Python, no build step, no compiled assets

## Learning objectives (skills practiced)
- Reading and extending an existing open-source tool's YAML config schema
- Structuring Docker Compose files for a stateless static server (volume mounts, port binding, restart policy)
- Applying config-as-code discipline: every dashboard change goes through `config.yml`, never via UI
- Understanding Homer's group → service model and mapping it to a curriculum phase structure
- Configuring health ping endpoints and understanding what Homer's status check actually does (HTTP HEAD/GET against a URL)
- Iterative maintenance: updating a config file as downstream projects come online

## Architecture / design note
```
homer-dashboard/
├── docker-compose.yml       # Defines the Homer container; mounts ./config into /www/assets
├── config/
│   └── config.yml           # Homer configuration; version-controlled; no secrets
├── config/assets/           # Optional: custom logo or favicon
└── Project.md
```

Key decisions to make explicitly:
- Use named Docker volume vs. bind mount: use a **bind mount** so `config.yml` is directly editable and committed
- Group projects by curriculum phase (Phase 1–6) so the dashboard reflects the learning arc
- Use Homer's `tag` and `subtitle` fields to surface project status (e.g., "live", "in progress", "not started")
- Pin the Homer image tag to a specific version after initial setup to avoid surprise breaking changes

## Test strategy
- **Smoke test:** `docker compose up -d` followed by `curl -f http://localhost:8080` must return HTTP 200
- **Config validation:** Homer logs a parse error on startup if `config.yml` is malformed — verify clean startup with `docker compose logs homer`
- **Link check:** manually verify that each documentation link opens the correct file or URL
- **Status ping check:** for at least one project with a health endpoint, confirm Homer's status indicator turns green; confirm it turns red when the endpoint is stopped
- **Secret check:** `grep -rE '(password|token|secret|key)' config/config.yml` must return nothing

## Documentation checklist
- [ ] `README.md` with run instructions and a screenshot of the running dashboard
- [ ] `config/config.yml` comments explaining each top-level section
- [ ] Inline doc block in `config.yml` describing how to add a new service entry
- [ ] Note on how to update the Homer image version safely

## API contract
No HTTP API. Homer is a static file server. The only interface is the browser UI at `http://localhost:8080`.

## UI / status surfaces
Homer's built-in browser dashboard. Groups map to curriculum phases. Each card shows: project name, one-line description, doc link, optional app link, optional status ping indicator.

## Security boundaries to think about
- Homer must be bound to `127.0.0.1` only — never `0.0.0.0` on a shared or remote machine
- `config.yml` must not contain API keys, passwords, or tokens; if a linked service needs auth, the link goes to its public URL only
- Docker socket must not be mounted into the Homer container
- Review Homer's default headers — it serves files directly, so there is no server-side logic to audit, but confirm no directory listing is exposed

## Profiling plan
Profile only if a performance question arises. Homer is a static file server; no performance work is expected.

## How this project fits into the curriculum
Phase 6, project 20 (after `terraform-k3s`). It has no hard dependencies and can be started any time, but it reaches full value only as downstream projects come online. It is a living document in container form — the config evolves with the curriculum rather than being completed once. It also reinforces config-as-code habits established in earlier infrastructure projects.

## Suggested milestone walkthrough
1. Read the Homer README and `config.yml` example — understand the group/service/item hierarchy before writing anything
2. Write a minimal `docker-compose.yml` that bind-mounts `./config` and exposes port 8080 on localhost only; confirm Homer starts
3. Draft `config.yml` with all 6 curriculum phases as groups and one placeholder service per phase; verify the dashboard renders
4. Add all 19 projects as service entries with their `README.md` and `Project.md` paths as documentation links
5. For each project that has a live URL or health endpoint, add it as the service `url` and enable `ping`
6. Write the "how to add a new project" section in `config.yml` comments and verify the secret check passes

## Reference notes and resources
- [Homer GitHub repo and config reference](https://github.com/bastienwirtz/homer)
- [Homer `config.yml` example](https://github.com/bastienwirtz/homer/blob/main/public/assets/config.yml.dist)
- [Docker Compose bind mount docs](https://docs.docker.com/compose/compose-file/05-services/#volumes)
- [Homer status/ping feature explanation](https://github.com/bastienwirtz/homer#status-indicator)
