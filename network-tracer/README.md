# Network Tracer

**Goal:** Explore host and container networking from a Go utility before examining packet payloads.

**Scope:** Local interfaces, routes, ARP/neighbour tables, active connections, and traceroute-style diagnostics; optional local HTML status view.

**Out of scope:** Broad network scanning, stealth, or packet capture (see the optional `packet-tracer` extension).

**Learning focus:** OS networking interfaces, routing, Docker bridges, permissions, and how reachability differs from application health.

**Depends on:** `go-fundamentals`, `go-http-server`.

## Milestones
- [ ] Report local interfaces and routes without elevated privileges.
- [ ] Inspect active connections and compare with a running worker.
- [ ] Add a traceroute-style diagnostic with explicit timeouts.
- [ ] Visualize local results and compare with `raft-adv` partition observations.
