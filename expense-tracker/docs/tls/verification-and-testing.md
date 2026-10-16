# TLS Verification and Testing

> How to *prove* a TLS deployment is correct without prior expertise — the exact
> commands, how to read their output, what each error means, and the checklist to run
> before sign-off. Everything here is runnable.

---

## 1. The three questions verification answers

1. **Is the cert valid and trusted?** — chain of trust, expiry, name match.
2. **What does this endpoint actually negotiate?** — protocol version, cipher suite.
3. **Is it configured the way I think it is?** — is the full chain present, is the
   right cert served, is SNI routed correctly.

You need all three. A cert that "looks fine" in the browser can still serve the wrong
chain to non-browser clients.

---

## 2. `openssl s_client` — the primary tool

```bash
openssl s_client -connect api.example.com:443 -servername api.example.com -showcerts
```

**Why every flag matters:**

| Flag | Purpose |
|------|---------|
| `-connect host:port` | where to connect |
| `-servername host` | **SNI** — without it you get the *default* cert, not the one for your hostname. This is the single most common verification mistake. |
| `-showcerts` | print every cert the server sends (leaf + intermediates) |

A minimal check (connect, print status, exit):

```bash
echo | openssl s_client -connect api.example.com:443 -servername api.example.com 2>/dev/null
```

### Reading the output — the fields that matter

```
depth=2 C = US, O = Internet Security Research Group, CN = ISRG Root X1
verify return:1                      ← client HAS this root in its trust store
depth=1 C = US, O = Let's Encrypt, CN = R11
verify return:1                      ← intermediate present and verified
depth=0 CN = api.example.com
verify return:1                      ← leaf present and verified
---
Certificate chain
 0 s:CN = api.example.com            ← the LEAF (server cert)
   i:CN = R11                        ←   signed by R11
 1 s:CN = R11                        ← the INTERMEDIATE
   i:CN = ISRG Root X1               ←   signed by the root
---
Server certificate
subject=CN = api.example.com
issuer=CN = R11
---
No client certificate CA names sent
Peer signing digest: SHA256
Server Temp Key: X25519, 253 bits     ← ECDHE key share (PFS in action)
---
SSL handshake has read 3456 bytes and written 923 bytes
Verification: OK                    ← ★ THE SUMMARY LINE
---
New, TLSv1.3, Cipher is TLS_AES_256_GCM_SHA384
Server public key is 2048 bit
Secure Renegotiation IS NOT supported
Compression: NONE
Expansion: NONE
No ALPN negotiated
SSL-Session:
    Protocol  : TLSv1.3
    Cipher    : TLS_AES_256_GCM_SHA384     ← the negotiated suite
    Verify return code: 0 (ok)              ← ★ 0 = everything verified
```

### The decision tree for reading `s_client`

```
                     ┌────────────────────────────────┐
                     │  Verify return code: 0 (ok)?   │
                     └───────────────┬────────────────┘
                          NO         │         YES
             ┌───────────────────────┼────────────────────────┐
             ▼                       ▼                        ▼
   ┌──────────────────┐   ┌────────────────────┐   ┌────────────────────┐
   │ code 10/18/19/20 │   │ code 21            │   │ Chain is VALID      │
   │ = missing/can't  │   │ = cert mismatch    │   │ → now check expiry, │
   │   verify         │   │ (leaf ≠ -servername│   │   protocol, cipher  │
   │   intermediate   │   │  or wrong cert)    │   │   (steps 3–5)       │
   └────────┬─────────┘   └─────────┬──────────┘   └────────────────────┘
            ▼                       ▼
   FIX: serve fullchain.pem   FIX: check the SNI/hostname
   on the server (not cert)   routing, and the cert's SAN list

   Other codes worth knowing:
     10 = EXPIRED                18 = SELF-SIGNED IN CHAIN
     19 = SELF-SIGNED LEAF       21 = UNABLE TO VERIFY FIRST CERT
     23 = not-yet-valid          24 = invalid CA (basic constraints)
```

The full list: `openssl errstr 21` (and any other code).

---

## 3. Inspecting a certificate file

```bash
# Full human-readable dump of a cert
openssl x509 -in cert.pem -text -noout

# Just the expiry date
openssl x509 -in cert.pem -enddate -noout
#  notAfter=Jan  8 00:00:00 2026 GMT

# Just the SANs (the field that actually matters)
openssl x509 -in cert.pem -noout -ext subjectAltName

# Just who issued it
openssl x509 -in cert.pem -noout -issuer -subject

# Does the private key match the cert? (compare the modulus/pubkey hashes)
openssl x509 -in cert.pem -noout -pubkey   | sha256sum
openssl pkey -in key.pem -pubout           | sha256sum
#   → these two hashes MUST match. A mismatch = wrong key = handshake failure.
```

**The key/cert match check is the one people forget**, and it's the cause of a
confusing class of failures where the cert looks fine but the handshake dies.

```bash
# Verify a local chain explicitly against a CA bundle
openssl verify -CAfile ca-bundle.pem fullchain.pem

# Is a cert expired, in one line, scriptable?
openssl x509 -in cert.pem -noout -checkend 0 \
  && echo "VALID" || echo "EXPIRED"

# How many seconds until expiry (for an alert)
echo $(( ($(date -d "$(openssl x509 -in cert.pem -noout -enddate | cut -d= -f2)" +%s) - $(date +%s) ))
```

---

## 4. What protocols and cipher suites are actually enabled

`openssl s_client` shows what *this one connection* negotiated. To enumerate
everything the server accepts:

```bash
# Probe each protocol version
for v in tls1 tls1_1 tls1_2 tls1_3; do
  printf "%-8s " "$v"
  echo | openssl s_client -$v -connect api.example.com:443 2>&1 \
    | grep -q "Cipher is" && echo "SUPPORTED" || echo "no"
done

# What you want to see: tls1_1 and tls1 no, tls1_2 and tls1_3 SUPPORTED.
```

Dedicated scanners give the full picture, including weak suites and known
vulnerabilities:

```bash
sslscan api.example.com:443          # fast, scriptable, in most distros
testssl.sh api.example.com:443       # thorough; grades and explains each finding
```

**What to flag:**

| Finding | Action |
|---------|--------|
| SSLv3 / TLS 1.0 / TLS 1.1 enabled | **disable** — POODLE, BEAST |
| RC4, 3DES, `*_CBC_*` suites | disable — Lucky13, Sweet32 |
| No forward secrecy (static RSA suites) | disable — ECDHE only |
| Weak cert key (< 2048-bit RSA) | reissue |
| Certificate expiring < 14 days | alert (see RB-11) |

---

## 5. Verifying the nginx-rendered config

The server may be serving a different cert than the one on disk if the config wasn't
reloaded. Check what's *actually* loaded:

```bash
# Inside the nginx pod
nginx -T                          # dumps the fully-rendered config (all vhosts)
nginx -T 2>/dev/null | grep -E 'ssl_certificate|server_name|listen .*443'
```

```
┌─────────────────────────────────────────────────────────────┐
│  THE MISMATCH THAT BITES:                                    │
│                                                              │
│   cert.pem on disk ─────►  nginx.conf points to it           │
│        │                            │                        │
│        └── renewed by cert-manager  └── still holds the OLD  │
│             (file changed)              cert in memory       │
│                                                              │
│   FIX: reload nginx (SIGHUP / `nginx -s reload`).            │
│   cert-manager does this via its webhook — verify it ran.    │
│                                                              │
│  DIAGNOSE: compare the SERIAL of what's served (s_client)    │
│  against the serial of the file (openssl x509 -serial).      │
│  Different serials = stale config.                            │
└─────────────────────────────────────────────────────────────┘
```

```bash
# Serial served by the server:
echo | openssl s_client -connect api.example.com:443 -servername api.example.com \
  2>/dev/null | openssl x509 -noout -serial
# Serial of the file:
openssl x509 -in /path/to/tls.crt -noout -serial
#   → must match
```

---

## 6. End-to-end verification from the client's perspective

```bash
# curl against the real name, using the system trust store
curl -v https://api.example.com/health 2>&1 | grep -E 'SSL connection|subject:|issuer:'

# Python, which uses its own CA bundle (certifi) — a common surprise
python3 -c "
import ssl, socket
ctx = ssl.create_default_context()
with socket.create_connection(('api.example.com', 443)) as s:
    with ctx.wrap_socket(s, server_hostname='api.example.com') as ss:
        print('protocol:', ss.version())
        print('cipher  :', ss.cipher()[0])
        print('cert    :', ss.getpeercert()['subjectAltName'])
"

# If you must use a self-signed cert on your own machine for testing
curl --cacert ./my-ca.pem https://api.example.com/health       # trust only this CA
# NEVER `curl -k` in anything but a one-off local test — it disables all verification
```

**`curl -k` / `--insecure`** turns off every check in this document. It's a debugging
crutch, not a configuration. If it's in a script, a CI job, or a container's
Dockerfile, that's the bug.

---

## 7. Reviewer checklist (run before sign-off)

- [ ] `openssl s_client -servername <host>` reports `Verify return code: 0 (ok)`.
- [ ] The served chain has the **leaf + all intermediates** (not just the leaf).
- [ ] The leaf's **SAN** list includes every hostname clients will use.
- [ ] Not After is comfortably in the future (> 30 days), and a renewal mechanism
      exists (RB-11 alert configured).
- [ ] The served cert's **serial matches the file's serial** (no stale config).
- [ ] Private key matches the cert (the modulus/pubkey hash check from §3).
- [ ] TLS 1.2 and 1.3 negotiate; TLS 1.0/1.1 do **not**.
- [ ] Only AEAD suites with ECDHE (`sslscan` / `testssl.sh` output reviewed).
- [ ] The key/cert pair is stored with `chmod 600`, never in git.
- [ ] If self-signed: the trust anchor is documented, and it's known that only
      machines with that anchor added will connect.

---

## 8. Interview angle

- **"How do you debug 'works in Chrome, fails in curl'?"** — the missing-intermediate
  case. Browsers do AIA chasing and cache; `curl` and most language HTTP clients do
  not. Fix is the full chain on the server.
- **"What does `Verify return code: 0 (ok)` actually tell you?"** — that the chain
  walked to a trusted root, names matched, and nothing is expired/revoked. It does
  *not* tell you the key strength, the negotiated protocol, or that the config is
  current.
- **"How do you check a cert without touching the server?"** — `s_client -servername`
  (SNI is essential), `-showcerts`, compare serials.
- **"Self-signed in production?"** — only with an explicitly managed trust anchor and
  a real reason; otherwise it's a broken trust model with extra steps.

---

## 9. How this shows up here

- The exact commands above are the verification path for the edge cert chosen in
  [`this-project-topology.md`](this-project-topology.md).
- The expiry check feeds the **RB-11 "TLS cert nearing expiry"** runbook in
  [`../runbooks.md`](../runbooks.md) — the alert should run the `-checkend` command
  and page before the deadline, not after.
- If Tailscale's own certs are used, verify those the same way — the tools don't care
  who issued the cert.
- The serial-match check (§5) is the specific guard against the stale-config failure
  that happens after every renewal.
