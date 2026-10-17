# TLS Topology for This Project

> How TLS actually composes here, in this specific deployment. The key thing beginners
> miss: **this project has two layers of encryption**, and they're independent. Get the
> layer model right and every other decision falls out.

---

## 1. The two layers

```
  ┌──────────────────────────────────────────────────────────────────┐
  │                                                                    │
  │  ┌──────────┐                                                      │
  │  │  client  │                                                      │
  │  │ (your    │                                                      │
  │  │ laptop)  │                                                      │
  │  └────┬─────┘                                                      │
  │       │                                                            │
  │       │  ════════════  TLS  ════════════                          │
  │       │  HTTPS over Tailscale. Terminates at NGINX.                │
  │       ▼                                                            │
  │  ┌──────────────────────┐                                          │
  │  │  Tailscale (WireGuard)│  ════════════  VPN ENCRYPTION  ═══════  │
  │  │  IP-layer tunnel      │                                          │
  │  │  (separate from TLS) │  every byte is encrypted                 │
  │  └──────────┬───────────┘                                          │
  │             │  ─────── plain ────────  but still inside the mesh   │
  │             │  (WireGuard encrypts at the IP layer;                 │
  │             │   TLS was already terminated at NGINX)                │
  │             ▼                                                       │
  │  ┌───────────────────────────────────────────────┐                 │
  │  │  NODE                                                                                  │
  │  │  ┌───────────┐   plain HTTP   ┌─────────────┐                │
  │  │  │  NGINX    │ ──────────────► │  API pod    │                │
  │  │  │ (terminates│                │ (DRF)       │                │
  │  │  │  TLS here)│                 └─────────────┘                │
  │  │  └───────────┘                                                 │
  │  │       ▲                                                        │
  │  │       │   plain HTTP (k8s pod network, inside the cluster)     │
  │  │  ┌────┴────┐                                                   │
  │  │  │  UI pod │                                                   │
  │  │  └─────────┘                                                   │
  │  └───────────────────────────────────────────────────────────────┘
  └──────────────────────────────────────────────────────────────────┘

  TWO INDEPENDENT ENCRYPTION LAYERS:
    1. TLS (HTTPS) between the client and NGINX — the *application* encryption
    2. WireGuard between the client's mesh endpoint and the node — the *network* encryption
```

**This is the picture to hold in your head.** Everything else is a decision that flows
from it.

---

## 2. Why both layers, and why they're orthogonal

```
  ┌───────────────────────────────────────────────────────────────┐
  │  Tailscale / WireGuard                                          │
  │    • Encrypts at the IP layer — everything on the wire between  │
  │      mesh endpoints is ciphertext.                              │
  │    • Solves: "can someone on the internet route to my node?"    │
  │      (no, only mesh endpoints).                                 │
  │    • DOES NOT solve: "who am I talking to?"                     │
  │      It doesn't establish HTTPS-level identity for the URL.    │
  │    • DOES NOT apply: inside the k3s pod network (already in-   │
  │      mesh, plain HTTP between pods).                            │
  │                                                                  │
  │  TLS                                                              │
  │    • Encrypts HTTP requests between the client and NGINX.       │
  │    • Solves: eavesdropping, tampering, and (with a valid cert)  │
  │      IMPERSONATION — proving the endpoint you reached is the   │
  │      one whose identity the cert names.                          │
  │    • Applies: only between client and NGINX. Once TLS is        │
  │      terminated at NGINX, everything inside the cluster is      │
  │      plain HTTP.                                                │
  │                                                                  │
  │  Neither replaces the other.                                     │
  │  • Removing Tailscale: your endpoint is now on the public net.  │
  │  • Removing TLS: the client has no proof of identity, and if    │
  │    WireGuard is ever misconfigured the traffic is cleartext.     │
  └───────────────────────────────────────────────────────────────┘
```

The classic misconception: "I'm already on Tailscale, why TLS?" Because:

1. **Identity.** WireGuard gives you a private pipe; it doesn't give you a cert
   chain. Two apps can't distinguish "talk to my real node" from "talk to whatever
   endpoint I pointed at" without TLS + a cert.
2. **Defense in depth.** If Tailscale is ever misconfigured, TLS is still there.
3. **Tooling.** Anything standard (`curl`, browser, `kubectl port-forward`
   inspection, health checks) works with HTTPS semantics and lets you verify with
   `openssl s_client` (see [`verification-and-testing.md`](verification-and-testing.md)).

---

## 3. Where to terminate TLS — and why here

```
  ┌───────────────────────────────────────────────────────────────┐
  │  CHOICE: where does TLS end?                                   │
  │                                                                 │
  │   A) Client → NGINX (TLS)  → NGINX → API (plain HTTP)         │
  │      ★ THIS PROJECT                                            │
  │      • Simplest. Standard pattern.                             │
  │      • NGINX is the only TLS-terminating component.            │
  │      • API pods don't need to know about TLS at all.            │
  │      • Cost: traffic inside the pod network is plain HTTP.     │
  │        (Mitigated: it's inside the cluster network AND inside  │
  │        the Tailscale mesh — double-network-bound.)              │
  │                                                                 │
  │   B) Client → NGINX (TLS)  → NGINX → API (TLS, mTLS)          │
  │      ✗ NOT HERE                                                │
  │      • Every service gets a cert, service-to-service is        │
  │        mutually authenticated. Real-world pattern for micro-   │
  │        services; overkill for a single-user single-node system │
  │        (marked "for scale").                                   │
  │                                                                 │
  │   C) Client → API directly (TLS at the app)                    │
  │      ✗ NOT HERE                                                │
  │      • Loses the centralized edge policy (rate limits, headers │
  │        all move to the app).                                   │
  │      • Also requires exposing the API directly, which conflicts│
  │        with Tailscale-only access.                             │
  └───────────────────────────────────────────────────────────────┘
```

**Termination at NGINX is the right call for this project** — it's the standard
ingress pattern and gives you a single point for all edge policy.

---

## 4. The three certificate choices

```
  ┌──────────────────────────────────────────────────────────────────┐
  │                                                                   │
  │  CHOICE 1: Self-signed cert                                       │
  │  ─────────────────────                                           │
  │  • openssl req -x509 -newkey ... -subj /CN=... -addext SAN:...    │
  │  • WORKS: yes — but only on machines where you added the cert     │
  │    to the trust store.                                            │
  │  • OVER TAILSCALE: fine for one user / one machine. You run      │
  │    `security add-trusted-cert -d /path/to/cert` on macOS or       │
  │    install to `/usr/local/share/ca-certificates/` on Linux.        │
  │  • DOESN'T WORK: any other machine, any CI script, any new user.  │
  │    Each time someone adds the cert manually.                       │
  │  • COST: zero.                                                    │
  │  • RECOMMENDED FOR: local dev, single-user, this project's first │
  │    iteration.                                                     │
  │                                                                   │
  │  CHOICE 2: Let's Encrypt + cert-manager (DNS-01 challenge)        │
  │  ────────────────────────────────────────────────                │
  │  • ACME protocol; cert-manager automates renewal                  │
  │  • OVER TAILSCALE: HTTP-01 won't work (no public port 80) —      │
  │    must use DNS-01 with a DNS provider that has an API.            │
  │  • Works if you own a real domain and have DNS API creds.         │
  │  • COST: a domain (5-20/yr), a DNS provider account, some setup. │
  │  • RECOMMENDED FOR: the "serious" version of this project, and   │
  │    anything with more than one user.                             │
  │                                                                   │
  │  CHOICE 3: Tailscale Serve / cert (Tailscale's own cert magic)    │
  │  ────────────────────────────────────────────────                │
  │  • Tailscale can serve HTTPS endpoints on mesh tailnets with     │
  │    auto-provisioned certs (tailnet-based ACME).                   │
  │  • WORKS: zero external dependencies; certs auto-renew.           │
  │  • REQUIRES: Tailscale Control Plane or MagicDNS setup.           │
  │  • RECOMMENDED FOR: mesh-only HTTPS with zero external infra.    │
  │    Very attractive for this project.                             │
  │                                                                   │
  └──────────────────────────────────────────────────────────────────┘
```

### What I'd actually pick, and why

```
  Phase 12 (first deploy):   Self-signed + `kubectl port-forward` OR
                             cert-manager with a local CA (step-ca) —
                             zero external setup, works offline.

  Later (production-shaped): cert-manager + Let's Encrypt via DNS-01,
                             or Tailscale's own HTTPS serving if you're
                             already using MagicDNS.
```

The important thing is that the *choice* is documented in `design.md`, not that any
one of them is universally "right."

---

## 5. The end-to-end picture with cert strategy

```
  CLIENT                                          NODE
    │                                               │
    │  1. TCP SYN over Tailscale/WireGuard (encrypted at IP layer)
    │ ────────────────────────────────────────────► │
    │                                               │
    │  2. TLS handshake:                             │
    │    ClientHello ────►                          │
    │        ◄─────── ServerHello, Certificate       │
    │  (client verifies the cert: chain → root in   │
    │   its trust store; SAN matches hostname)      │
    │                                               │
    │  3. Application data, HTTPS (TLS inside the   │
    │    WireGuard tunnel)                           │
    │ ────── GET /api/v1/expenses ─────────────────► │
    │                                               │
    │                       ┌────────────────────────┐
    │                       │  NGINX terminates TLS  │
    │                       │  ───► plain HTTP ────► │── API pod
    │                       └────────────────────────┘
    │                                               │
    │  4. Response (HTTPS)                          │
    │ ◄────── 200 OK, JSON ──────────────────────── │
```

**One specific point worth naming:** the client verifies the certificate *during* the
TLS handshake, but the TLS handshake itself is happening inside a WireGuard tunnel.
That means:
- The handshake is protected from eavesdropping by WireGuard.
- The identity proof (the cert) is still TLS's job.
- WireGuard doesn't see anything inside the TLS records; TLS doesn't know it's inside
  WireGuard. They just compose.

---

## 6. What to record in `design.md`

```markdown
## TLS and trust boundary decisions

- **Where TLS terminates:** NGINX ingress. Plain HTTP inside the pod network.
- **Certificate provider:** [self-signed for now / Let's Encrypt via DNS-01 / Tailscale]
  - Renewal mechanism: [manual / cert-manager]
- **Certificate type:** [RSA 2048 / ECDSA P-256]
- **Expiry alerting:** runs the `-checkend` command from
  `verification-and-testing.md` and alerts at [14] days.
- **What's in the SAN:** api.example.com, [others]
- **Trust anchors required on the client:**
  - Tailscale's Control Plane cert (for mesh connectivity)
  - Our cert (or its CA) — [how it's installed]
- **Explicitly out of scope:** service mesh / mTLS between pods (single node,
  single user; revisit if we ever add users or a second node).
```

---

## 7. Interview angle

- **"How does encryption work between the client and a private-node service?"** — two
  independent layers: TLS between client and NGINX for identity + app encryption;
  WireGuard/VPN between client and node for network encryption. Naming both and why
  neither replaces the other is the answer.
- **"Why TLS inside a VPN?"** — identity (WireGuard doesn't do cert chains), defense
  in depth, and interoperability with standard HTTPS tooling.
- **"Where would you terminate TLS?"** — at the ingress, once, centrally; anything
  deeper adds certs to every service and is overkill until you need it.
- **"What's the right cert strategy with no public ingress?"** — DNS-01 ACME (real
  domain) or Tailscale's mesh-native HTTPS serving; HTTP-01 doesn't work.

---

## 8. How this shows up here

- The whole diagram in §5 is what you'll actually run.
- The three cert choices in §4 are the *actual* options you're choosing between at
  Phase 11; whichever you pick goes into `design.md`.
- The "plain HTTP inside the cluster" choice is deliberate and documented — the
  alternative (mTLS) is a real pattern but is overkill for this project.
