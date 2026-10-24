# 03 — The TCP handshake: the first three packets of a flow

A *flow* is not "a request." It is a *TCP connection*, and a connection *begins* with a *three-way handshake*. The handshake is the *first three packets* of *every* TCP flow you will ever capture. *Reading* them is the *fastest* way to tell *what* happened in a flow, *without* reading the *payload*.

## The three packets, and what each one *is*

```
   client                          server
     │                               │
     │  ── 1. SYN ─────────────────►│   "I want to connect. My ISN = x."
     │                               │
     │  ◄──────────────────── 2. SYN+ACK  │   "ok. My ISN = y."
     │                               │
     │  ── 3. ACK ─────────────────►│   "ok. connection is open."
     │                               │
     │  (data flows both ways)       │
     │                               │
     │  ── 4. FIN ─────────────────►│   "I am done."
     │  ◄──────────────────── 5. ACK │
     │  ◄──────────────────── 5'. FIN │   "I am done too."
     │  ── 6. ACK ─────────────────►│   "connection is closed."
```

| Packet | flags | What the *server* is saying | What the *client* is saying |
|---|---|---|---|
| 1 | `SYN` | — | "open; ISN=x" |
| 2 | `SYN+ACK` | "open; ISN=y" | — |
| 3 | `ACK` | — | "confirmed; I will use your ISN=y" |

*After* the handshake, *both* sides send `ACK`-only or *data* packets (the `ACK` bit is *set* on *every* packet after the handshake, *except* the very first `SYN`). *Before* the handshake, *only* `SYN` and `SYN+ACK` exist.

## The *sequence numbers* make it a *state machine*, not a *message*

The handshake is not "the client sends three messages." It is a *state machine* with *one shared counter* (the *seq space*). The *key* fact:

- The `SYN` packet *occupies* seq `x` (the ISN). Its `seq` field is `x`.
- The `SYN+ACK` *occupies* seq `y` (the server ISN). Its `seq` is `y`; its `ack` is `x+1`.
- The client's `ACK` *has no data*. Its `seq` is `x+1`; its `ack` is `y+1`.

*After* the handshake, the *data* packets *continue* the counter: the *first* data byte from the client is at seq `x+1`. *Every* data segment *advances* the seq by *its length + 1* (the +1 is *why* a `FIN` *consumes* a seq number — it is a *zero-length* packet that *still* advances the counter by 1).

## How the parser *reads* the handshake, *field by field*

For each of the first three packets, *read*:

1. **`flags`** (byte 13 of the L4 header, `02` doc): `SYN` (`0x02`), `ACK` (`0x10`).
2. **`seq`** (bytes 4–7 of L4): the *current* seq.
3. **`ack`** (bytes 8–11 of L4): the *next expected* seq on the *other* side.

The *three-packet* *signature* of a *handshake*:

| Packets 1-2-3 | flags | seq | ack |
|---|---|---|---|
| 1 | `SYN` (no ACK) | `x` | 0 |
| 2 | `SYN+ACK` | `y` | `x+1` |
| 3 | `ACK` (no SYN) | `x+1` | `y+1` |

*If* the three packets do *not* match that *shape*, it is *not* a *normal* handshake. The *other* shapes:

- **`SYN` → `SYN+ACK` → ... and *no* third `ACK`:** the connection is *half-open*. The *client* did not *confirm*. Either the client is *gone*, or a *SYN flood* (an *attack* — see the *security* note in `04`).
- **`SYN` → `RST`:** the *server* *refused*. The port is *not* listening. The *flow* is *one* packet (`SYN`) + *one* (`RST`), not three.
- **`SYN` → `ACK` → `RST`:** the *server* accepted the `SYN`, the client sent an `ACK`, but the *connection* was *reset* *immediately*. A *firewall* or a *connection-limit* is the usual cause.

The *parser* reports *which* shape it saw, *per flow*. That *shape* is the *one* field that tells you *how the connection ended*, *without* reading the payload.

## The *RST* is the *abnormal* close

A *clean* close is the *two*-`FIN` dance at the *bottom* of the diagram: *each* side *independently* sends a `FIN`, *each* side *ACKs* the other's `FIN`. *Four* packets (`FIN`, `ACK`, `FIN`, `ACK`).

A *`RST`* is the *abnormal* close: *one* side *tears down* the connection *unilaterally*. The *counterpart* does *not* get to say "bye"; it just *gets a `RST`* and *stops*. The *causes*:

- A *process* *died* while *holding* the socket (the *kernel* sends a `RST` on its behalf).
- A *firewall* *dropped* the *state* and *RSTs* the *orphan* packets.
- A *connection* *timed out* and the *kernel* *RSTs* it.
- A *SYN flood* (see `04`): the *kernel* *RSTs* the *overflow*.

*Every* flow that ends in a `RST` is *abnormal*. A flow that ends in *two* `FIN`s is *clean*. The *ratio* of *RST-closes* to *FIN-closes* is a *health signal*: a *high* RST ratio is a *process* dying, a *firewall* dropping, or a *capacity* *limit* hit.

## The *round-trip* the handshake *reveals*

The *time* between *packet 1* and *packet 2* is *one* RTT (client → server, the `SYN`). The *time* between *packet 2* and *packet 3* is *another* RTT (server → client, the `SYN+ACK`; client → server, the `ACK`). The *total* handshake *time* is *~2 RTT* + the *server's* *response* time.

*Reading* the *timestamps* of the *three* packets (the *capture* tool *records* a *timestamp* per *packet*), you *compute* the *RTT*:

```
rtt ≈ (t[SYN+ACK] - t[SYN])          # one way, client→server
rtt ≈ (t[ACK]    - t[SYN+ACK])       # one way, server→client + client→server
```

*The two* RTTs *should* be *close* (within the *asymmetry* of the *path*). A *large* asymmetry is a *path* problem, not a *host* problem. The *parser* reports the *rtt_est* per flow (the *average* of the *handshake* RTTs).

## Where this shows up in the *lab*

`labs/read-a-handshake.md` gives you *three* captured TCP packets (the *SYN*, the *SYN+ACK*, the *ACK*) with *timestamps* and *seq/ack* fields. You *read*:

1. *Are* the three *flags* in the *handshake* shape? (SYN, SYN+ACK, ACK.)
2. *Do* the *seq/ack* *fields* *line up*? (SYN seq=x, SYN+ACK ack=x+1, ACK ack=y+1.)
3. *What* is the *RTT*? (The *two* *time* *deltas*.)
4. *How* did the flow *end*? (Two `FIN`s = clean; a `RST` = abnormal.)

*The* four *questions* *are* the *whole* *diagnosis* *of* a *TCP* *flow*, *without* *reading* the *payload*. *That* is the *power* of *header-only* *observation*.
