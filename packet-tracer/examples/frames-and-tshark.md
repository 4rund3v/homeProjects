# Reference frames and tshark snippets

These are *illustrative* shapes, not a real capture. The point is the *field layout*, not the exact values. Use them with the labs; the labs say *what to read*, these say *where it is*.

## frames.hex (one frame per line, annotated)

```
# 1) Clean HTTP, TCP/80, no VLAN, ihl=5, dataoff=5
#    L2 (14 B) | L3 IP (20 B) | L4 TCP (20 B) | L7 "GET /api/products HTTP/1.1 ..."
#    L3 start=14, ihl=5 → L4 start=34, dataoff=5 → L7 start=54

# 2) TLS record, TCP/443
#    Same offsets, but L7 is a TLS record (type=0x17 application data, length=4096).
#    The parser STOPS at L4 — L7 is encrypted.

# 3) ARP (L2 type 0x0806)
#    No L3/L4/L7. Peel STOPS at L2. (The "ARP" opcode: 1=who-has, 2=reply.)

# 4) ICMP echo-request (L3 proto 1)
#    L4 is ICMP (type 8=echo-request, 0=echo-reply, 11=ttl-exceeded). No ports.
```

Generate a real one for the lab (lab-originated only, per `../Project.md`):

```
# Capture 10 packets from the lab interface, 60 s
sudo timeout 60 tcpdump -i <lab-iface> -w /tmp/lab.pcap 'not (udp port 514)'

# Decode the four layers of frame N
tshark -r /tmp/lab.pcap -Y "frame.number == N" \
  -e eth.type -e ip.proto -e tcp.srcport -e tcp.dstport -e tcp.flags -e _ws.col.info

# The whole flow of a 5-tuple, as packets
tshark -r /tmp/lab.pcap -Y "ip.addr == <src> and tcp.port == <dst>" \
  -e frame.time_relative -e tcp.flags -e tcp.seq -e tcp.ack -e tcp.len
```

## The SNI leak query (the TLS hostname)

```
tshark -r /tmp/lab.pcap -Y "tls.handshake.extensions_server_name" \
  -e tls.handshake.extensions_server_name
```

The SNI is readable *without the key*. That is the `04` "hostname leak."

## tshark display-filter cheat (the ones the labs use)

| Filter | Selects |
|---|---|
| `tcp.flags.syn == 1 and tcp.flags.ack == 0` | *SYN-only* (the first handshake packet) |
| `tcp.flags.reset == 1` | *RST* (abnormal close) |
| `tcp.flags.fin == 1` | *FIN* (clean close) |
| `tcp.port == 443` | the TLS flows |
| `dns` | the DNS queries (UDP/53) |
| `arp` | the ARP frames |

Each is a *display filter* — a *where* clause over the *dissected* fields. The *parser* in `../Project.md` reproduces the *same* selections in Go; the tshark filter is the *reference* for "did the parser stop at the right layer."

## The flow-summary shape (what the parser emits)

```
# One line per 5-tuple, the whole lab capture
<srcIP>:<srcPort> -> <dstIP>:<dstPort>  proto=<tcp|udp>  pkts=N bytes=M
    flags=<SYN,SYN+ACK,ACK,...>  first=<t0> last=<t1>  end=<FIN|FIN|FIN|RST>
    l7=<http|tls|dns|icmp|arp|unknown>
```

`l7` is the *inference* from the port (`02`'s port table), *not* a *read* of the payload. `end` is the *last* flag pair, which tells you *how the connection closed* (`03`).

The *summary* is *safe* by construction: it has **no payload bytes**, only *headers*, *counts*, *timestamps*, and *flag shapes*. That is the `04` "the parser sees headers, not content."
