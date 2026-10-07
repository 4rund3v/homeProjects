# Packet Tracer (Optional Extension)

**Goal:** Observe real network traffic safely on an isolated lab to understand what a network can and cannot reveal, complementing `network-tracer` and `raft-adv` experiments.

**Scope:** Capture and display traffic on a dedicated isolated lab interface; identify protocols, endpoints, and a small set of flows; understand capability models (for example `CAP_NET_RAW`) and sandboxed alternatives.

**Out of scope:** Broad scanning, traffic injection or manipulation, and capturing traffic not originated by the lab. Security review, isolation, and legal/capacity boundaries are first-class.

**Learning focus:** The difference between observing network state and controlling network behavior; what visibility a sidecar or node can have inside a local lab; how live capture failures teach system boundaries.

**Depends on:** `network-tracer`, host capability model, explicit isolation policy.

## Milestones
- [ ] Define an isolated lab environment and confirm the capture boundary before any code.
- [ ] Capture traffic with provided PCAP files; demonstrate parsing without live access.
- [ ] When live capture is allowed, add a safe capture mode, permission checks, and limited retention.
- [ ] Visualize flow summaries only; write what is visible and what is not, and how that differs from `network-tracer` and Raft partition simulations.

## Tools
- Go pcap bindings, Wireshark/tshark for validation, Docker capability controls, and strict lab network boundaries.
