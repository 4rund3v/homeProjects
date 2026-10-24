# Lab: peel a frame by hand, then verify with tshark

## Prereqs

- The four hex frames in `examples/frames.hex` (one per line: a clean HTTP, a TLS record, an ARP, an ICMP).
- `tshark` on the host (or Wireshark). A `sample.pcap` from `../testdata/` if you want to cross-check.

## The by-hand pass (the understanding)

For *each* of the four frames, *before* touching `tshark`, *compute*:

1. **The L2 `type` field** (bytes 12–13). What does it say the L3 is?
2. **The L3 start offset** (`14`, or `18` if there is a VLAN tag at `0x8100`).
3. **The L3 `ihl`** (lower nibble of byte 0 of L3) → the L3 header length.
4. **The L4 start offset** (`L3start + ihl×4`).
5. **The L4 `proto`** (byte 9 of L3) → TCP / UDP / ICMP.
6. **The stop condition**: does the peel *end* at L3 (ARP/ICMP) or continue to L4/L7?

Write the answers in a *table*, one *row* per *frame*:

```
frame   L2.type  L3start  ihl  L4start  proto  stop-at  L7 readable?
http    0x0800   14      5    34       6      L7       yes (port 80)
tls     0x0800   14      5    34       6      L4       no  (TLS, port 443)
arp     0x0806   —      —    —        —      L3       —
icmp    0x0800   14      5    34       1      L3       —
```

## The tshark pass (the verification)

For each frame, *cross-check* the *by-hand* *table*:

```
# Decode the L3/L4/L7 layers of frame N
tshark -r sample.pcap -Y "frame.number == N" \
  -e ip.id -e ip.proto -e tcp.srcport -e tcp.dstport -e tcp.flags -e _ws.col.info
```

*Compare* the *`proto`* and *port* you *read by hand* against the *`tshark`* *output*. If they *disagree*, the *pointer* you *misread* is the *bug* — *re-read* `01` (the offsets) and `02` (the stop conditions). The *tool* is *correct*; your *peel* is not.

## The follow-up questions

- The *HTTP* frame's `type` is `0x0800`. What is the *byte* value of the *IP `ihl`* field, and what is `ihl×4`? (The lower nibble of the first IP byte. Usually `5` → `20`.)
- The *TLS* frame's L4 is `TCP/443`. Why does the peel *stop* at L4 and *not* read L7? (The L7 is a *TLS record* — *encrypted*. `04` is the doc.)
- The *ICMP* frame's `proto` is `1`. Why is there *no* L4? (ICMP *is* the L3 protocol — it has *no* L4/ports. The peel *stops* at L3. `02`.)
