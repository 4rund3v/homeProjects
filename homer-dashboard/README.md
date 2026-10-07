# homer-dashboard
**Goal:** Deploy Homer as a local landing page that links every curriculum project's docs, app URL, and health status.

**Scope:** Docker-based Homer deployment, YAML config version control, service/group layout for all 19 curriculum projects, status ping configuration.

**Out of scope:** Custom code, authentication, public exposure, automated config generation.

**Learning focus:** Docker container configuration, Homer service/group YAML model, config-as-code discipline, rolling maintenance as projects come online.

**Depends on:** None (can be started immediately; entries are added as projects mature).

## Milestones
- [ ] Run Homer in Docker with a minimal config that reflects the full curriculum structure (groups and placeholder entries)
- [ ] Add all 19 projects as documentation entries with links to their `README.md` and `Project.md`
- [ ] Add live app URL and status ping entries for each project as it comes online (rolling task)
- [ ] Document the `config.yml` schema and write a how-to for adding a new project entry
