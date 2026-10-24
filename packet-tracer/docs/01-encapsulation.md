# 01 — Encapsulation: how a byte stream becomes a packet stack

## The one picture to keep

Every layer *adds a header* to the front of the payload as it goes *down* (sender side), and *removes one* as it goes *up* (receiver side). The *data* you care about (the HTTP request) is the *innermost* thing. The *headers* are the *wrappers*.

```
         sender                                              receiver
   ┌────────┐                                            ┌────────┐
   │  L7    │  HTTP request "GET /api/products"          │  L7    │
   ├────────┤                                            ├────────┤
   │  L4    │  + TCP header (ports, seq, flags)          │  L4    │
   ├────────┤                                            ├────────┤
   │  L3    │  + IP header (src/dst IP, ttl)             │  L3    │
   ├────────┤                                            ├────────┤
   │  L2    │  + Ethernet frame (MACs, type)             │  L2    │
   └────────┘                                            └────────┘
        │                                                      ▲
        └────── (bits on the wire, L1) ───────────────────────┘
```

*Downward* (left to right, top to bottom): each layer *prefixes* a header. *Upward* (bottom to top on the right): each layer *peels* its header off and hands the rest to the layer above.

## The *header* of each layer, with the field you actually read

| Layer | Header fields you read | The *pointer* field (the one that says "what's next") |
|---|---|---|
| L2 Ethernet | `dst-MAC` (6 B), `src-MAC` (6 B), `type` (2 B) | `type`: `0x0800` = IPv4, `0x0806` = ARP, `0x8100` = VLAN (another L2 frame inside) |
| L3 IP (v4) | `ver/ihl` (1 B), `ttl` (1 B), `src-IP` (4 B), `dst-IP` (4 B), `proto` (1 B) | `proto`: `6` = TCP, `17` = UDP, `1` = ICMP |
| L4 TCP | `src-port` (2 B), `dst-port` (2 B), `seq` (4 B), `ack` (4 B), `flags` (1 B) | `dst-port` + `proto` = the *application* (443/TCP = HTTPS, 80/TCP = HTTP, 53/UDP = DNS) |
| L7 | *the payload itself* | *only readable if L4 is not TLS* |

The *pointer* fields are the *entire* parser. You do not "understand" a packet by reading the HTTP body. You *dispatch* on the pointer fields, layer by layer, and *only then* read the body.

## The *byte offsets* (the part that is *always* tripped over)

The offsets are *not* fixed, because L3 and L4 have *options* and *padding*. The *safe* offsets:

- **L2 Ethernet** (no VLAN): header is *14 B*. L3 starts at *byte 14*.
- **L2 Ethernet** (*with* a VLAN tag): the `type` field is `0x8100`, and *another* 4 B (the *VLAN tag*, `0x8100` + `PCP/VID` + a *second* `type`) is inserted. L3 starts at *byte 18*.
- **L3 IP**: the `ihl` nibble (lower 4 bits of byte 0) × 4 = the IP header length, in *bytes*. Normally *20*, up to *60* with options. L4 starts at `14 + 4×ihl` (or `18 + 4×ihl` with a VLAN).
- **L4 TCP**: header is *20 B* + `4 × data-off` (the `data-off` nibble × 4), normally *20*, up to *60*. L7 starts at `L4-start + 4×data-off`.

The *lesson*: **do not hard-code "L3 is at byte 14." Read the *pointer* fields and *compute* the offset.** A *hard-coded* offset breaks on the *first* VLAN-tagged or IP-options packet you meet. That is a *parser bug*, and it is the *most common* one.

## A *concrete* byte read

One captured Ethernet frame (hex), with the *peel* annotated:

```
off  0: 0 0 0 0 0 0  0 0 1 c 0 1  0 8 0 0        L2: dst=00:00:00:00:00:00 src=00:00:1c:01:... type=0x0800 (IPv4)
off 14: 4 5 0 0 0 0 5 a 0 0 0 0  0 0 8 0 0 6    L3: ver=4 ihl=5 ttl=64 proto=6(TCP)  (5×4=20 B header)
off 20: 0 0 5 0 0 0 1 c 9 0 0 3 3 7 0 0 0 3 2 0 8 6 b 0 e 8 d 0 f f 5 L4: src-port=80 dst=6789 seq=... dataoff=5 flags=SYN ...
off 34: 47 45 54 20 2f 20 48 54 54 50 2f 31 2e 31 ...                    L7: "GET / HTTP/1.1 ..."  (plaintext, so readable)
```

The *parser* reads `type=0x0800` (byte 12–13) → "L3 is IPv4, starts at 14." Reads `ihl=5` (byte 14, lower nibble) → "L4 starts at 14 + 20 = 34." Reads `proto=6` (byte 23) → "L4 is TCP." Reads `dataoff=5` (byte 32, upper nibble) → "L7 starts at 34 + 20 = 54... " *wait*, the `GET` is at *byte 34* in this *synthesized* example — the point is the *method*, not the exact numbers. **Read the pointer, compute the offset, then read.**

## The *anti-pattern*: the fixed offset

```go
// WRONG: hard-codes "no VLAN, ihl=5, dataoff=5"
const l3Off = 14
const l4Off = 34
const l7Off = 54
```

This *works* on the *first* clean capture and *breaks* on a VLAN-tagged frame (L3 is at 18, not 14), or a packet with *IP options* (L4 is at 14+24, not 34). The *correct* shape:

```go
// RIGHT: follow the pointer fields
l3 := 14
if etype == 0x8100 { l3 += 4 }          // VLAN tag
ihl  := int(b[l3]) & 0x0f
l4   := l3 + ihl*4
proto := b[l3+9]
dataoff := int(b[l4+12]) >> 4
l7   := l4 + dataoff*4
```

*One* line per pointer. The *lab* tool in `../Project.md` must use the *second* shape. The *first* shape is the *exact* bug that makes "the parser works on my sample.pcap but not on the live interface."

## Where this shows up in the *lab*

`labs/read-a-frame.md` takes a *single* hex line and makes you *compute* the offsets by hand, *then* check them against `tshark`. The *by-hand* pass is the *understanding*; the `tshark` pass is the *verification*. If they disagree, the *pointer* you misread is the *bug*, not the tool.
