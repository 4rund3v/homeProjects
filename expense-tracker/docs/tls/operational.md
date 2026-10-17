# TLS in Production — Operations

> The operational problems that actually happen to TLS deployments — cert expiry, chain
> ordering, key rotation, renewal automation — and how to handle each. If you read
> [`how-it-works.md`](how-it-works.md) for the protocol and
> [`verification-and-testing.md`](verification-and-testing.md) for the debugging, this
> is the *ongoing* part.

---

## 1. The failure mode that causes most TLS outages

```
  ┌────────────────────────────────────────────────────────────────┐
  │  "My cert expired."                                            │
  │                                                                  │
  │  It always looks the same from the outside:                     │
  │    ERR_CERT_DATE_INVALID / "certificate has expired"            │
  │  and there's usually NOTHING wrong with anything except that    │
  │  today is after `notAfter`.                                     │
  │                                                                  │
  │  The fix is boring: automate renewal, and alert on approaching  │
  │  expiry.                                                         │
  │                                                                  │
  │  This is the #1 cause of TLS outages in the industry, full      │
  │  stop. Not exotic attack, not misconfiguration — expiry.        │
  │                                                                  │
  │  Runbook for this project: RB-11 in runbooks.md.                │
  └────────────────────────────────────────────────────────────────┘
```

**The rule:** the *expiry alert* must fire **N days before** the cert expires, not on
the day. Let's Encrypt uses 90-day certs *because* that's how much warning you need
to fail gracefully.

**Concrete thresholds:**

```
  Cert issued                    Days until expiry   Action
  t=0                            90                  ✓ no action
  t=75                           15                  ⚠ alert (RB-11)
  t=85                           5                   🚨 page
  t=90                           0                   ✗ outage

  A reasonable alert fires at ≤14 days; page at ≤5 days.
```

The check itself is a one-liner (see
[`verification-and-testing.md`](verification-and-testing.md) §3):

```bash
# How many days until this cert expires?
openssl x509 -in /etc/tls/tls.crt -noout -enddate | cut -d= -f2
# → notAfter=Jan  8 00:00:00 2026 GMT

# Programmatic check with an alert threshold:
days=$(( ( $(date -d "$(openssl x509 -in /etc/tls/tls.crt -noout -enddate | cut -d= -f2)" +%s) - $(date +%s) ) / 86400 ))
[ "$days" -le 14 ] && echo "ALERT: cert expires in $days days"
```

---

## 2. ACME / cert-manager renewal — what actually happens

```
  ┌───────────────────────────────────────────────────────────────┐
  │  Timeline (Let's Encrypt, 90-day certs)                        │
  │                                                                 │
  │  t=0      cert issued                                          │
  │  t=60     cert-manager runs `check` — still valid, no action   │
  │  t=75     cert-manager starts trying to renew                  │
  │             • runs the DNS-01 challenge                        │
  │             • signs the CSR, gets a new cert                    │
  │  t=75+d   new cert written to the Secret                       │
  │             • controller reloads nginx with the new chain       │
  │  t=90     (old cert would have expired here, but renewal       │
  │           already succeeded ~15 days earlier)                   │
  └───────────────────────────────────────────────────────────────┘

  ┌───────────────────────────────────────────────────────────────┐
  │  WHY "renew at 75 days" and not 89?                            │
  │                                                                  │
  │  Cert-manager defaults to renewing when ≤30 days remain,         │
  │  and tries continuously until success.                          │
  │  Leaving margin protects against:                                │
  │    • a failing DNS-01 challenge (rate-limited, DNS API creds    │
  │      expired, DNS propagation slow)                             │
  │    • a stuck Secret sync (k8s cache, controller restart)        │
  │    • the classic "I forgot to renew, and my alert was broken"    │
  │                                                                  │
  │  Real-world: renewal should ALWAYS complete well before         │
  │  expiry. If it takes >7 days, you have a real problem.           │
  └───────────────────────────────────────────────────────────────┘
```

### The chain-of-trust pitfall: missing intermediate

```
  ┌────────────────────────────────────────────────────────────────┐
  │  The secret cert-manager writes has TWO files:                  │
  │    tls.crt   = the LEAF cert only                               │
  │    tls.key   = the private key                                  │
  │                                                                  │
  │  If nginx is configured with just `tls.crt`, it serves ONLY the │
  │  leaf. Clients without AIA chasing fail with                    │
  │  "unable to get local issuer certificate".                      │
  │                                                                  │
  │  FIX: use `tls.crt` = the FULL CHAIN (leaf + intermediates).   │
  │  In cert-manager the field is often:                            │
  │    .status.notAfter + .status.chain                             │
  │  or the annotation `cert-manager.io/revision` is irrelevant;     │
  │  the point is you must concatenate leaf + intermediate and      │
  │  serve that as `tls.crt`.                                       │
  │                                                                  │
  │  Symptom: works in your browser (Chrome does AIA chasing),      │
  │  fails in curl, Python, mobile, some APIs.                       │
  │  See verification-and-testing.md §2 for how to verify.         │
  └────────────────────────────────────────────────────────────────┘
```

### The stale-config trap after renewal

```
  ┌────────────────────────────────────────────────────────────────┐
  │  cert-manager renews the cert. The Secret is updated.           │
  │  Now what?                                                      │
  │                                                                  │
  │  If the ingress controller doesn't reload nginx, the OLD cert   │
  │  stays in memory and gets served until something triggers a     │
  │  reload.                                                        │
  │                                                                  │
  │  Symptom: cert-manager shows the new cert in the Secret, but    │
  │  `openssl s_client -connect host:443` shows the old serial.     │
  │                                                                  │
  │  Check: are the serials equal?                                  │
  │    echo | openssl s_client -connect host:443 -servername host  │
  │        2>/dev/null | openssl x509 -noout -serial                │
  │    openssl x509 -in /etc/tls/tls.crt -noout -serial             │
  │  Same serial → nginx is current. Different → reload nginx.      │
  └────────────────────────────────────────────────────────────────┘
```

---

## 3. One cert, many domains

```
  Option A: one cert per host
    api.example.com     → cert1
    app.example.com     → cert2
    Status: many certs, many renewal cycles, many files.

  Option B: wildcard cert
    *.example.com       → cert (covers api, app, sub.foo.example.com)
    Status: one cert, but:
      • Doesn't cover example.com itself (only subdomains)
      • Covers ALL subdomains, including typos and unused ones
        → any subdomain is potentially reachable, so typosquatting
          risk if your DNS is lax
    Status: fine if you actually use the wildcard.

  Option C: multi-SAN cert (the modern default)
    api.example.com, app.example.com, docs.example.com  → ONE cert
    Status: one cert with multiple SANs. Best for a fixed set of hosts.
```

For this project, **multi-SAN** is the natural choice: enumerate the hosts you
actually expose.

---

## 4. Private key lifecycle

```
  ┌───────────────────────────────────────────────────────────────┐
  │  Key rotation, storage, and blast radius                       │
  │                                                                 │
  │  STORAGE                                                     │
  │  • Dev / single user: a k8s Secret. Fine on your own node.     │
  │  • Real infra: Vault PKI or a cloud KMS. Key material          │
  │    never leaves the HSM — you call "sign this" and the HSM     │
  │    signs. A leaked filesystem backup leaks nothing.            │
  │  • NEVER: in a container image, in a git repo, in a log line. │
  │                                                                 │
  │  ROTATION                                                    │
  │  • ACME-managed certs rotate automatically (the new cert        │
  │    comes with a new key by default).                           │
  │  • Self-signed certs: rotate manually when you notice, or by    │
  │    cron.                                                       │
  │  • If your app holds long-lived TLS sessions, key rotation      │
  │    can affect resumption (see tls-1.3.md §6 for session        │
  │    ticket keys).                                              │
  │                                                                 │
  │  BLAST RADIUS OF A LEAKED KEY                                 │
  │  • Without PFS: decrypt ALL past traffic that was recorded.     │
  │    The whole history is compromised.                            │
  │  • With ECDHE (TLS 1.3 default): past sessions are safe.       │
  │    Only NEW sessions going forward can be decrypted.            │
  │    → This is why PFS is the single most important property     │
  │      for a compromised key.                                    │
  │                                                                 │
  │  What to do if the key is leaked:                              │
  │    1. Revoke the cert (if CA-signed) via CRL / OCSP.           │
  │    2. Reissue a new cert with a fresh key.                     │
  │    3. Rotate session ticket keys (TLS 1.3).                    │
  │    4. Assume new traffic since the leak is compromised; old   │
  │       is safe IF you had PFS.                                  │
  └───────────────────────────────────────────────────────────────┘
```

---

## 5. Monitoring cert expiry from inside the system

```
  ┌───────────────────────────────────────────────────────────────┐
  │  THE TWO FLAVORS OF "CERT EXPIRY"                               │
  │                                                                  │
  │  A) The cert is a FILE you can read                              │
  │     → run `openssl x509 -enddate` on a cron                     │
  │     → compare with today, alert on ≤N days                     │
  │                                                                  │
  │  B) The cert is in an EXTERNAL CA (Let's Encrypt)                │
  │     → your secret has the current cert                          │
  │     → monitor the `.status.notAfter` field on the Certificate   │
  │     resource, or the tls.crt in the Secret                      │
  │     → cert-manager also has a `Certificate` status                │
  │       field `Ready: False` when a renewal is failing — ALERT    │
  │       ON THIS TOO, NOT JUST EXPIRY                              │
  └───────────────────────────────────────────────────────────────┘
```

The key subtlety: **a cert can be about to expire but cert-manager can't renew it** —
because your DNS API creds expired, or you hit the ACME rate limit, or the challenge
propagation is broken. Your alert must catch:
1. The cert's actual expiry date.
2. `Certificate.Ready = False` from cert-manager (the renewal is stuck).
3. Any `CertificateRequest` stuck in `Failed` state.

Alerting on expiry alone misses the case where the *renewal* is broken but the cert is
still valid for another week. By then it's too late to have margin.

---

## 6. Why TLS on an already-private network

```
  ┌───────────────────────────────────────────────────────────────┐
  │  "I'm on Tailscale. It's already encrypted. Why TLS?"           │
  │                                                                  │
  │  Because "private network" is an ASSUMPTION.                     │
  │                                                                  │
  │  1. WireGuard protects traffic IN TRANSIT between mesh           │
  │     endpoints. It doesn't prevent a compromise of one mesh      │
  │     endpoint from reading traffic ON that endpoint.              │
  │     If your node is compromised, whatever protocol you used      │
  │     between the client and NGINX was already broken anyway.     │
  │                                                                  │
  │  2. WireGuard gives you a private pipe but no IDENTITY.          │
  │     Two different machines can present identical TLS-less        │
  │     HTTP endpoints. TLS + a cert is how the client verifies     │
  │     which endpoint it reached.                                  │
  │                                                                  │
  │  3. Tooling works better with HTTPS: `curl`, browsers,           │
  │     health checks, kubectl port-forward, monitoring agents       │
  │     — they all understand HTTPS semantics natively.              │
  │                                                                  │
  │  4. Defense in depth is the point.                              │
  │     The whole point of running two layers is that if one        │
  │     assumption is wrong, the other still holds.                 │
  └───────────────────────────────────────────────────────────────┘
```

The answer to "why not just HTTP inside the mesh?" is: because then any compromise
of the mesh, or any misconfiguration of the mesh, becomes an immediate compromise of
the traffic. TLS costs almost nothing here and buys you one more layer.

---

## 7. Interview angle

- **"Your cert is about to expire. What do you check?"** — the `.status.notAfter` on
  the Certificate resource, the actual file's enddate via `openssl x509 -enddate`, and
  — critically — whether cert-manager's `Ready` field is False (renewal broken).
- **"ACME renewal is broken but the cert is still valid. Alert?"** — Yes. Alert on
  `Certificate.Ready=False` and on any stuck `CertificateRequest`, not just on
  approaching expiry.
- **"TLS cert leaked. What do you do?"** — revoke, reissue with new key, rotate
  session-ticket keys, and know that with PFS only *new* traffic is compromised.
- **"Why TLS inside an encrypted VPN?"** — identity (certs), defense in depth, and
  tooling interop.
- **"Multi-SAN vs wildcard vs one-cert-per-host?"** — SAN is the modern default for a
  fixed host set; wildcard is broad but requires you to actually use every subdomain;
  one-per-host is a maintenance nightmare.

---

## 8. How this shows up here

- **RB-11 in `../runbooks.md`** is the runbook this doc supports. It should:
  1. Check the cert's expiry date with `openssl x509 -enddate`.
  2. Check `kubectl get certificate` shows `Ready: True`.
  3. Check `kubectl get certificaterequest` has no stuck entries.
  4. Alert at 14 days remaining; page at 5.
- The renewal mechanism (self-signed cron vs cert-manager) is a decision that goes in
  [`../design.md`](../design.md).
- If the choice is DNS-01 (see
  [`certificates-and-pki.md`](certificates-and-pki.md) §5.2), the operational
  dependency is the DNS API creds in your Secret — the renewal silently breaks when
  they expire. Worth calling out explicitly.
- If Tailscale's own HTTPS serving is used, the "expiry" problem disappears — but so
  does the ability to verify without trusting Tailscale's CA. Trade-off, not free
  lunch.
