# 02 — The four-step peel, in the order the parser runs it

This doc is the *algorithm*. `00` is *what*; `01` is *the bytes*; this is *the sequence*. The Go parser in `../Project.md` is a *direct* transcription of these four steps.

## The peel, as a decision tree

```
read a frame (one contiguous byte slice)
│
├─ 1. L2: is it Ethernet?  (magic on a real capture: the frame starts with a dst-MAC that is not all-zero)
│     read `type` at off 12-13.
│     ├─ 0x8100  → VLAN: skip 4 B, read the *inner* type at off 16-17.
│     ├─ 0x0800  → IPv4. Go to step 2.
│     ├─ 0x86dd  → IPv6. Go to step 2 (the IPv6 header is fixed 40 B; read `next-header` at off 6).
│     └─ 0x0806  → ARP. No L3/L4/L7. Summarize as "ARP" and stop.
│
├─ 2. L3 (IPv4): `ihl` = (b[0] & 0x0f) × 4. `proto` = b[9].
│     ├─ 6 → TCP. Go to step 3.
│     ├─ 17 → UDP. Go to step 3 (UDP header is 8 B; ports at off 0-3).
│     └─ 1 → ICMP. Summarize as "ICMP" (types: 8=echo-request, 0=echo-reply, 11=ttl-exceeded). Stop.
│
├─ 3. L4 (TCP): `dataoff` = (b[12] >> 4) × 4. Ports at off 0-3 (src) and 4-5 (dst).
│     flags at off 13 (SYN, ACK, RST, FIN, PSH, *read as a 1-byte* bitfield).
│     seq at off 4-7, ack at off 8-11.  (The seq/ack pair is *how* the handshake is read — `03`.)
│
└─ 4. L7: only if (proto == 6 AND dst-port == 80) or (src-port == 80).
        └─ read the bytes as HTTP. Look for "GET ", "POST ", "HTTP/".
        If L4 is TCP/443, L7 is *TLS* — do NOT read it as HTTP. Summarize as "TLS (encrypted)."
```

## The *port-to-application* table (the L7 inference)

The *only* way to guess L7 from L4 is the *port* (because L7 is not *on the wire* when it is encrypted). The *small* set you need for this lab:

| L4 | Implied L7 | Readable? |
|---|---|---|
| TCP/80 | HTTP | yes (plaintext) |
| TCP/443 | HTTPS (TLS) | *no* (encrypted) |
| UDP/53 | DNS | *partially* (the *question* is plaintext, the *answer* may be encrypted in DNSSEC) |
| TCP/5432 | Postgres | *partially* (the *startup* packet is plaintext; the *query* may be encrypted) |
| TCP/6379 | Redis | *partially* (RESP is plaintext unless AUTH/TLS is on) |
| TCP/9092 | Kafka | *no* (binary protocol) |

The *senior* read: **the port is a *hint*, not a *fact*.** A port-80 TCP stream *could* be an SSH tunnel or a non-HTTP service. The *hint* is what you *assume* for a *summary*; the *fact* is "I *cannot* tell without decrypting."

## The *TCP flags* byte (the one field that *matters* for the handshake)

The flags are a *single byte* with *named* bits, at *offset 13* of the TCP header (after `dataoff`, `window`, `checksum`):

| Bit (high→low) | FIN | SYN | RST | PSH | ACK | URG |
|---|---|---|---|---|---|---|

Read it as: `flags := b[13]; syn := flags & 0x02 != 0; ack := flags & 0x10 != 0; fin := flags & 0x01 != 0; rst := flags & 0x04 != 0`.

A *SYN* with *no* ACK = "I want to open a connection." A *SYN+ACK* = "you can open it." A *FIN* = "I want to close it." A *RST* = "tear it down *now*." The *sequence* of these is the *handshake* — `03`.

## The *sequence* field is *why* you can order packets

TCP is *stateful* and *ordered*. The `seq` number is a *counter* that *increments* by the *payload length* of each *data* segment. A *SYN* packet consumes *one* seq number (the *ISN*); a *FIN* consumes *one*; a *data* segment consumes *len+1*. This is why the *capture tool* can *re-order* out-of-order segments and *reconstruct* the *byte stream* of a *flow*. The *parser* in `../Project.md` does *not* re-order (that is *Wireshark's* job); it *reads* the `seq` and *reports* it.

## The *stop* conditions (when the peel *ends*)

The peel *ends* early in three cases, and the *parser must handle all three* or it will *crash on the first one*:

1. **ARP / a non-IP L2 type.** There is *no* L3. *Stop* at step 1.
2. **ICMP.** There is *no* L4/L7 in the usual sense. *Stop* at step 2 (report the *ICMP type*).
3. **An encrypted L4.** TLS / a binary protocol. *Stop* at step 3 (report "encrypted, length N"). Do *not* *try* to read L7.

The *anti-pattern* is a parser that *assumes* "there is always an HTTP body at the end." That *assumption* is the *exact* thing that makes "the parser works on my sample.pcap" — because *sample.pcap* is *curated* to be *clean*. The *real* capture has *ARP*, *ICMP*, *TLS*, and the parser *must* *stop* on each.

## The *summary* the parser emits (the *output* shape)

Per *flow*, *one* line, *flow-keyed* (the *flow key* is the 5-tuple: `src-IP, src-port, dst-IP, dst-port, proto`):

```
FLOW  192.168.1.10:53 → 1.1.1.1:443 (TCP, TLS)  packets=28 bytes=41023  flags=SYN,SYN+ACK,...,FIN  rtt_est=32ms
FLOW  192.168.1.10:53 → 1.1.1.1:443 (TCP, TLS)  ... (the *same* flow, *continued*)
```

The *flow* is the *unit* of the *summary*, not the *packet*. *Ten* packets that share a 5-tuple are *one* flow. The *parser* *aggregates* per 5-tuple. That *aggregation* is *summarize.go* in `../Project.md`.

## Where this shows up in the *lab*

`labs/peel-by-hand.md` gives you *six* hex frames (clean HTTP, TLS, ARP, ICMP, a *VLAN* frame, a *TCP* *with* *options*) and makes you *compute* the *stop* condition and the *summary* line *by hand*. The *six* cases are *exactly* the *stop* conditions *above*. If you can *peel* all six *by hand*, the *parser* is *just* the *mechanical* version of what you *did*.
