# Network Tracer

## What this project exists to solve
Learn to observe local network state safely and turn observations into useful diagnostics. This project complements `raft-adv`: knowing what "unreachable" looks like at the host level makes Raft partition behavior tangible.

## Success criteria / completion metrics
- A working Go CLI that reports interfaces, routes, active sockets, and a basic traceroute-style path without requiring live packet capture.
- An optional local status UI served over HTTP using the HTTP service patterns; omitted initially if the CLI is not yet correct.
- CI format/test/build pipeline for the Go CLI and optional image.
- Documented comparison between `network-tracer` (state observation) and `raft-adv` (partition simulation), and between this project and the optional `packet-tracer` (payload observation).

## Prerequisites and dependencies
- `go-fundamentals`, `go-http-server` (for the optional status UI).
- Understanding of OS networking from system documentation or a short orientation discussion before coding.

## Tools, libraries, and runtime
- Go toolchain.
- OS-provided network sources: `/proc/net/` on Linux, `netlink`, or a well-scoped library.
- Optional: `gopsutil` for cross-platform consistency or platform-specific parsing for learning.
- Optional local HTTP status UI reusing `go-http-server` patterns.
- Docker; optional local image and CI.

## Learning objectives (skills practiced)
- OS network primitives: interfaces, IP addressing, routing tables, ARP/neighbor tables, active sockets.
- Go parsing of structured data sources; error handling for absent or privileged sources.
- Docker networking: bridge, veth, iptables chains, and how containers appear to the host.
- Reachability vs. health: how a route exists but a host is unreachable.
- When elevated privileges are required and how to document that boundary.
- Local containerization and CI for Go CLI tools.

## Architecture / design note
CLI-first with a subcommand per diagnostic concern:

```
cmd/tracer/main.go
internal/
  interface.go   # interface enumeration
  route.go       # route table parsing
  neighbor.go    # ARP/neighbor table
  socket.go      # active connection listing
  hop.go         # traceroute-style reachability with bounded TTL/timeouts
  serve.go       # optional HTTP status UI
```

Keep each subcommand independently runnable and testable. The HTTP status UI is added only after the CLI is correct, because visualization without correct data is misleading.

## Test strategy
- Unit tests against synthetic/recorded OS output (do not rely on host networking state).
- Negative tests: absent files, permission-denied sources, malformed entries.
- Integration tests in CI on Linux with a controlled network namespace or container if feasible; skip if CI is a simple local runner without namespace support.

## Documentation checklist
- `README.md` with setup, subcommands, example outputs, OS assumptions (Linux-first), and permission notes.
- `NOTES.md` relating host/container network state to `raft-adv` partition experiments.
- Docker and CI notes with limitations (e.g., container networking differs from host).

## API contract
None. The optional status UI exposes simple diagnostic endpoints; document if present.

## UI / status surfaces
Optional local status page listing interfaces, routes, and recent observations. Serve over HTTP only after the CLI is correct.

## Security boundaries to think about
- Do not perform broad scanning or discovery on networks you do not own.
- Reading `/proc/net/` requires normal user privileges on Linux; reading some sources may require `CAP_NET_ADMIN`. Document and fail gracefully.
- Filter output so that only intended information is surfaced; do not print raw credentials or tokens if observed on a socket.

## Profiling plan
Profile is not the focus. A simple before/after measurement of subcommand latency is acceptable if the implementation has multiple approaches; otherwise defer to `profiling-lab` style only when a real question arises.

## How this project fits into the curriculum
Provides context for `raft-adv` partitions and validates that "a route exists" is not the same as "a host is reachable." Reuses `go-http-server` patterns only for the optional UI.

## Suggested milestone walkthrough
1. **Interfaces and routes.** Print interfaces and routes without elevated privileges; run on host and inside Docker and compare outputs.
2. **Neighbors and sockets.** Add ARP and active-socket reporting; explain what each column means.
3. **Reachability.** Add traceroute-style hops with bounded TTL and explicit timeouts; document what reachable and unreachable look like.
4. **HTTP status UI (optional).** Serve observations using the shared service patterns; do not build a large frontend.
5. **Container + CI.** Build an image; CI runs format, vet, tests, and image build.
6. **Raft-adv comparison.** Run the tracer alongside `raft-adv` partitions; document what each layer shows and why both matter.

## Reference notes and resources
- Linux `ip` and `ss` man pages.
- `proc(5)` man page for `/proc/net/` formats.
- Docker networking documentation (bridge, iptables, veth).
- Go `net` package and platform-specific interfaces.
