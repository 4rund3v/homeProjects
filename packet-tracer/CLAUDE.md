# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **concept-first** packet-capture learning lab. Two layers:

- **`docs/`** — the *theory*: what a packet is, encapsulation, the four-step peel, the TCP handshake, and the TLS/privacy boundary. Read these in order (`00` → `04`).
- **`Project.md` + `README.md`** — the *lab tool*: a small Go pcap parser that emits **flow summaries** (never payloads). This is the *consequence* of the docs.
- **`labs/`** — by-hand exercises: peel a frame, read a handshake, map the TLS boundary. Each lab has a *by-hand* pass (the understanding) and a `tshark` pass (the verification).
- **`examples/`** — reference frames, tshark filter cheats, and the summary shape.

## Invariant: the parser sees headers, not content

Every piece of work here obeys one rule: **output is a flow summary (5-tuple + flag shapes + counts + timestamps), never payload bytes.** If a lab or a snippet ever prints an HTTP body or a header value, it is a *bug* — the boundary is `docs/04`.

## The boundary is the interface, not the code

Capture scope is enforced by the **lab interface** (an isolated VLAN / dedicated port), *before* any capture code runs. The tool still checks permissions (`CAP_NET_RAW`) and lab boundaries and reports "not allowed" clearly rather than failing cryptically. PCAP-first: the parser must run on a *file* before it may touch a *live* interface.

## What a "good" answer is in this repo

A good answer names **which OSI layer** a thing lives at, **which pointer field** dispatches it, and **what is and is not visible** once TLS is on. Concretization over abstraction: cite the exact field offset (`ihl` at byte 0 of L3, `flags` at byte 13 of the TCP header, `type` at bytes 12–13 of L2) and the exact tshark filter.

## Anti-goals

- No live capture outside the lab interface. No traffic injection/manipulation.
- No retained raw payloads. No unbounded retention.
- Do not "improve" the parser to *read* encrypted content — the boundary *is* the lesson.
- No dependency on `network-tracer` (host state) or `raft-adv` (partition sim); this repo is *packet-level observation* only.
