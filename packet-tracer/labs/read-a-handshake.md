# Lab: read a TCP handshake, header-only

## Prereqs

- The three captured packets in `examples/handshake.pcap` (a clean 3-way handshake + a clean FIN close).
- `tshark`.

## Read the three packets *by hand*, then verify

For *each* of the first three packets of the flow, read:

1. **`flags`** — is it `SYN`, `SYN+ACK`, or `ACK`? (The bitfield, `03`.)
2. **`seq`** — the *current* seq. For the `SYN`, this is the client ISN (`x`).
3. **`ack`** — the *next expected* seq on the other side. For the `SYN+ACK`, this is `x+1`.

Fill the shape table from `03`:

```
pkt  flags     seq      ack
 1   SYN       x        0
 2   SYN+ACK   y        x+1
 3   ACK       x+1      y+1
```

## Then answer the four diagnostic questions

1. **Is the handshake shape *normal*?** (SYN → SYN+ACK → ACK, with the seq/ack fields lining up as above.)
2. **What is the *RTT*?** `tshark` gives you timestamps. Compute `t[SYN+ACK] − t[SYN]` and `t[ACK] − t[SYN+ACK]`. *Are they close?*
3. **How did the flow *end*?** Look at the *last* packets of the flow:
   - *Two `FIN`s* (one per side, each ACKed) = **clean** close.
   - *A `RST`* = **abnormal** close (`03`).
4. **RST or FIN ratio**: of the flows in the capture, how many end in `RST` vs `FIN`? A *high* RST ratio is a *health* signal.

## The tshark check

```
tshark -r handshake.pcap -Y "ip.addr == 192.168.1.10 and tcp.port == 443" \
  -e frame.time_relative -e tcp.flags -e tcp.seq -e tcp.ack
```

*Compare* your *by-hand* `seq/ack/flags` against the *tshark* output. The *two* should *match*. If they do not, the *field* you misread is the bug — re-read `03`.

## Follow-up

- The `SYN` packet's `ack` field is `0`. Why is it `0` and not some seq? (The `SYN` *opens* the connection — there is *no* *expected* seq on the *other* side *yet*. The `ack` field is *meaningless* on a `SYN`.)
- The `ACK` (pkt 3) has *no* data, but its `seq` is `x+1`. Why did the seq *advance* with no data? (The `SYN` *consumed* seq `x`. The `ACK` *continues* at `x+1`. The seq advances by *payload length + 1*; a zero-length ACK still advances by the `+1` *of the* *prior* *SYN*.)
- If pkt 2 were *missing* (no `SYN+ACK`), what would the *flow* look like? (A *half-open* connection — `SYN` sent, no response. A *firewall* dropped it, or the server is *down*. `03`.)
