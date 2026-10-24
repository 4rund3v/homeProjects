# Lab: what you can and cannot see (the TLS boundary)

## Prereqs

- `examples/tls-vs-http.pcap` — one flow over plaintext HTTP (port 80), one flow over TLS (port 443), *both* from the lab.
- `tshark`.

## The side-by-side

For *each* flow, list *what the parser could read* and *what it could not*:

### The HTTP/80 flow

```
tshark -r tls-vs-http.pcap -Y "tcp.port == 80" -e http.request.method -e http.request.uri
```

Readable: **method, URI, and the headers** (including `Authorization`, if present). The *entire* L7 is *plaintext*.

### The TLS/443 flow

```
tshark -r tls-vs-http.pcap -Y "tcp.port == 443" -e tls.handshake.extensions_server_name -e tls.version -e tls.handshake.type
```

Readable: **the SNI** (the hostname, in the *ClientHello*), **the cipher / version**, **the handshake shape** (ClientHello, ServerHello, ...). *Not* readable: **the HTTP request, the body, the response.**

## Fill the table (from `04`)

```
flow     SNI readable?   cipher readable?   HTTP method readable?   body readable?
HTTP/80  — (plaintext)    —                 yes                     yes
TLS/443  yes (SNI)       yes               no                      no
```

## The *leak* you must name

The SNI is *readable* on a TLS flow, *without the key*. That is the *one* piece of the *destination* that *is not* encrypted in a TLS 1.2 ClientHello. A *capture* that *does not* hold the key *can* see *which host* you *talked to*, even *not* the *what* you *sent*. **Name it out loud: the SNI is the hostname leak.**

## Follow-up

- The HTTP/80 flow's `Authorization: Bearer <token>` is *plaintext on the wire*. If a *capture* held it, what is the *consequence*? (A *secret leak* — the token is *in* the capture. This is *why* the *lab* emits *summaries*, not payloads.)
- The TLS/443 flow's SNI says `shop.local`. Could the SNI *lie*? (Yes — the SNI is *unauthenticated*. A *MITM* *could* send a *ClientHello* with *any* SNI. The SNI is a *hint* to the *server*, not a *credential*.)
- The *cipher* the TLS flow negotiated — is it the *strongest* available? (Read the cipher suite from the *ServerHello*. A *weak* cipher is a *finding*, even if the *payload* is *encrypted*.)
