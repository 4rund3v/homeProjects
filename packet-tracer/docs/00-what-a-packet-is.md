# 00 — What a packet actually is, and what you can see

A *packet* is not a "message." It is a *fixed-shape record* that carries, at the same time: *who it is for* (address), *who sent it* (source), *what kind of data it is* (protocol), and *the data* (payload). Every layer of the network *wraps* the record in a header, and every layer on the receiving side *peels* one header off. That wrapping is **encapsulation**, and it is the single most important concept in this project.

## What "seeing a packet" means

When you capture traffic (the *lab* tool in `../Project.md`), you are reading a *byte stream* off a link. You see:

- **Headers, always.** Every header is *plaintext* on the wire (except when the payload is encrypted). You can read the source/dest MAC, the IP, the port, the TCP flags, the HTTP method (if unencrypted).
- **Payload, *sometimes*.** If the payload is *encrypted* (TLS), you see the *length* and the *cipher*, not the *content*. You can see "a 2 KB TLS record," not "the JSON inside it."

The *boundary* between "always visible" and "encrypted" is the *first* thing a senior engineer internalizes: **you see the *routing* of a request, not the *content*, once TLS is on.**

## The shape, top to bottom

A single HTTP GET, captured at the *wire*, is *five* headers stacked on top of the request:

```
┌──────────────────────────────────────────────────────────┐
│  L1: bits (volts / light)                                │  ← Physical
├──────────────────────────────────────────────────────────┤
│  L2: Ethernet frame  [dst-MAC | src-MAC | type]          │  ← Data Link
├──────────────────────────────────────────────────────────┤
│  L3: IP packet       [ver | ttl | src-IP | dst-IP]       │  ← Network
├──────────────────────────────────────────────────────────┤
│  L4: TCP segment     [src-port | dst-port | seq | flags] │  ← Transport
├──────────────────────────────────────────────────────────┤
│  L7: HTTP request    "GET /api/products HTTP/1.1 ..."    │  ← Application
└──────────────────────────────────────────────────────────┘
```

Each box is a *header* (L2 through L4) plus the *payload* (L7). The *capture tool* reads the *whole stack* at once, because on the wire it is *one byte stream*. The *dissection* (what the Go parser in `../Project.md` does) is the *peeling*: identify L2, then L3, then L4, then L7, in that order.

## What the parser must do, in order

1. **Read the L2 header.** The *Ethernet type* field (`0x0800` = IPv4, `0x0806` = ARP, `0x8100` = VLAN) tells you *what the L3 layer is*. This is a *pointer*, not data.
2. **Read the L3 header.** The *IP protocol* field (`6` = TCP, `17` = UDP, `1` = ICMP) tells you *what the L4 layer is*.
3. **Read the L4 header.** The *ports* + the *protocol* (TCP vs UDP) tell you *what the L7 layer is* (TCP/443 = HTTPS, TCP/80 = HTTP, UDP/53 = DNS).
4. **Read the L7.** *Only if unencrypted.* If L4 is TCP/443, the L7 is *a TLS record* and you *cannot* read the HTTP inside it. If L4 is TCP/80, the L7 is *plaintext HTTP* and you *can*.

That *four-step peel* is the entire parser. `docs/02` is a *step-by-step* of that peel. `docs/03` is the *TCP handshake* (the first *three* packets of a connection). `docs/04` is *what TLS changes* (step 4 becomes "you cannot read it").

## The rules of the lab (carried from `../Project.md`)

- **PCAP first, live capture second.** The parser must work on a *file* before it may touch a *live* interface.
- **Flow summaries, not payloads.** The *output* is "53 flows, 40 HTTP, 13 TCP-only, 2 DNS." *Not* the *content* of any HTTP body.
- **Retention limits.** A capture holds *N* flows, then *drops* the oldest. No *unbounded* retention.
- **Legal boundary.** Only traffic the *lab* originated. The *boundary* is the *interface*, not the *code*.

The *docs* in this folder build the *concept*. The *lab tool* in `../Project.md` *implements* it. Read the docs *first*; the tool is the *consequence*.
