# Packet Tracer (Optional Extension)

## What this project exists to solve
Observe real network traffic safely on an isolated lab to understand what a network reveals and what it does not. This is distinct from `network-tracer` (host state observation) and from `raft-adv` (partition simulation). It exists to make the boundary of "observation" explicit.

## Success criteria / completion metrics
- PCAP parsing demonstrated on supplied sample files without live capture; the same parser later accepts live traffic only in a documented lab.
- A small Go program identifies protocols, endpoints, and flow summaries with strict retention and scope limits.
- Lab boundaries (interface, hosts, duration, retention) are defined and enforced before any capture code runs.
- A clear statement of what this project can and cannot show compared to `network-tracer` and `raft-adv`.

## Prerequisites and dependencies
- `network-tracer`; understanding of host network state.
- Explicit isolation policy and host capability model.
- `go-fundamentals`.

## Tools, libraries, and runtime
- Go pcap bindings.
- Wireshark/tshark for validation.
- Docker capability controls and isolation.
- Supplied PCAP files for the no-live-capture stage.

## Learning objectives (skills practiced)
- Packet capture concepts: interfaces, filters, promiscuous mode, and legal/capacity boundaries.
- Protocol dissection: headers, payload boundaries, and what metadata is visible.
- Capability models: `CAP_NET_RAW`, container sandboxing, and what observation permits vs. what control permits.
- Safe defaults: supplied PCAP first, live capture only in an explicit, limited lab.
- The difference between seeing packets and seeing application-level events.

## Architecture / design note
This is a lab tool with strong guards:

```
cmd/tracer/main.go
internal/
  capture.go         # capture interface with permission checks
  parse.go           # protocol dissection (limited scope)
  summarize.go       # flow summaries, not full payloads
  lab.go             # lab boundary enforcement
testdata/
  sample.pcap
```

Capture code must check permissions and lab boundaries before opening an interface. If live capture is not allowed, the tool should still parse PCAP files and report on them.

## Test strategy
- Tests against supplied PCAP files for parser correctness.
- Permission tests: tool reports "not allowed" clearly rather than failing cryptically.
- Boundary tests: retention limits, filter scope, and interface restrictions enforced.

## Documentation checklist
- `README.md` with lab policy, permission requirements, legal and capacity boundaries, and safe defaults.
- `NOTES.md` comparing what this project shows vs. `network-tracer` vs. `raft-adv` partition simulation.
- Wireshark/tshark validation steps.

## API contract
None. CLI-only by default; local HTTP UI is acceptable if it adds value but is not required.

## UI / status surfaces
Optional flow summary view; minimal and focused on observability, not inspection of payload content.

## Security boundaries to think about
- Live capture requires explicit host capabilities; default to PCAP-only.
- Do not capture traffic not originated by the lab; treat this as a lab boundary, not a technical limitation only.
- Limit retention and scope; do not retain raw payloads.
- Document what is visible (headers, sizes, protocols) and what is not (encrypted payload content without keys).

## Profiling plan
Profile is not the focus.

## How this project fits into the curriculum
Optional extension. It complements `network-tracer` and `raft-adv` by showing what packet-level observation can and cannot reveal about distributed-system behavior. If live capture is not available, PCAP parsing still teaches protocol dissection.

## Suggested milestone walkthrough
1. **PCAP parsing.** Parse supplied PCAP files; summarize protocols and endpoints without live capture.
2. **Lab policy.** Write the lab boundary document before adding any live capture.
3. **Permission checks.** If live capture is allowed, add capability checks and graceful denial.
4. **Live capture (optional).** Capture within lab boundaries; summarize flows with strict retention.
5. **Comparison notes.** Document what this project shows vs. `network-tracer` vs. Raft partition simulation.

## Reference notes and resources
- Go pcap library documentation.
- Wireshark display filters and protocol reference.
- Linux capability documentation (`CAP_NET_RAW`).
- Local lab network design and isolation practices.
