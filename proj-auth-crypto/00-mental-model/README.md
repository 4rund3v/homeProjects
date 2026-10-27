# 00 — The Mental Model: The Whole Thing in One Diagram

**Folder:** `00-mental-model/`

Before any tool, any command, any "use X" — internalize the vocabulary and the *shape* of the problem. Every folder that follows is a zoom-in on a region of this diagram. Get this wrong and the token layer will look like magic; get it right and the primitives (01–03) are just pieces of it.

---

## Teach first: the three verbs that get conflated

Authentication, authorization, and identity are three different questions people blur into one. Split them or you can't reason about a single credential.

| Verb | The question | The answer | The proof you carry |
|---|---|---|---|
| **Identity (Id)** | *Who are you?* | A stable, unique subject (`sub`) | A user ID, a service-account name, a cert subject |
| **Authentication (Authn)** | *Prove you are who you say you are* | A verified claim of that identity | A password check, a token with a valid signature, a certificate that chains to a trusted CA |
| **Authorization (Authz)** | *Are you allowed to do this thing?* | A yes/no on a specific resource + action | A role, a scope, an RBAC `Role`, a policy decision |

> **The mechanism, not the label.** A *token* is not authentication — it is **evidence of authentication that a third party can check without calling back.** You proved "I am Alice" to the IdP (that was authn). The IdP minted a signed token that *says* "Alice." Now the resource server can accept "Alice" without re-proving it. **The token is a transferable proof, and the signature is what makes it transferable.** That one sentence is 60% of the whole project.

### Identity is the noun; the other two are verbs that act on it

- **Identity** has no verification — it's just a name. `sub = user-12345`.
- **Authn** attaches *trust* to the identity: "I've confirmed this really is `user-12345`."
- **Authz** attaches *policy* to (identity, action): "can `user-12345` read `doc-7`?"

The reason the split matters to a panel: **you can have any two without the third.**
- Identity + Authn, no Authz: a public API key — anyone who proves they hold it can do the one thing it does.
- Authn, no stable identity: a one-time password — proof of being-a-person, but no persistent subject.
- This is why **service accounts (06)** exist: a *machine's* identity + authn, with Authz via RBAC. And why **OAuth scopes (05)** are Authz that got stapled onto an Authn token.

---

## What a token actually *is* (the panel's first question)

Strip away "JWT" and "OAuth." A **token** is a **bearer credential**: a piece of data whose *possession* implies a claim, and which a holder can present to a party who can independently verify the claim.

Three properties separate a *useful* token from a *dangerous* one:

1. **Verifiable without a phone call.** The verifier holds a key (or a hash, or a JWKS) that lets it check the token's integrity *locally*. This is what makes tokens scalable — the resource server never has to round-trip to the IdP on every request.
2. **Integrity, not secrecy.** A signed token is *not* encrypted. Anyone who reads it can read the claims. The signature guarantees *no one modified it* and *who made it* — not *who can read it*. (Encryption and signing are different primitives — that's all of 03.)
3. **Bounded validity.** `exp` + a short life + a `jti` that can be revoked. A token that lives forever is a credential leak waiting to happen.

> **Threshold — "bearer" is the load-bearing word.** Because a token proves by *possession*, "whoever holds this token is that subject" is the default. Everything in 04/05/06 is about **reducing the blast radius of a stolen bearer credential**: short `exp`, rotating refresh tokens, scoping, binding to a client, revocation.

---

## The three-legged OAuth dance

OAuth/OIDC (05) has **four actors** but the *dance* is three-legged. Name them and nothing in 05 is confusing:

```
────────────────────────────────────────────────────────────────────────────────
────────────────────────────────────────────────────────────────────────────────
   │ Owner (RO)   │          (the human user)                    │  Provider (IdP) │
────────────────────────────────────────────────────────────────────────────────
────────────────────────────────────────────────────────────────────────────────
        ▲                                                      ▲
        │                                                      │
        │ 2. "Alice, did you really authorize this app?"      │
        │    (redirect to the IdP's login page)               │
────────────────────────────────────────────────────────────────────────────────
────────────────────────────────────────────────────────────────────────────────
   │  Server (RS)     │    (the app that wants a      │   "Outline" / your │
   │  "the API"       │     token, e.g. to read Alice) │   app             │
────────────────────────────────────────────────────────────────────────────────
```

- **Resource Owner (RO)** = the human. Owns the *resource* (their data).
- **Client (C)** = the app the human is using. It wants to act on the RO's behalf.
- **Identity Provider (IdP) / Authorization Server** = the party that *knows who the RO is* and can vouch for them. This is the trust anchor.
- **Resource Server (RS)** = the API that holds the data. It trusts the IdP's token, **not** the Client directly.

**OAuth (the authorization part)** answers "the RO let Client C access *this scope* of the resource." **OIDC (the identity part, 05)** adds "and here is *exactly who the RO is* — a signed ID token (a JWT, 04)."

The **leg** that makes it a dance: the RO never gives the Client a password. The RO authenticates *to the IdP*; the IdP issues a *short, scoped, signed token* to the Client; the Client uses it against the RS. **Each leg is separable, which is why a system can have a client secret (Client↔IdP), a refresh token (Client's session), and a service-account cert (machine↔machine) all coexisting (06, 07).**

---

## Why each layer exists — the whole stack, bottom-up

This is the diagram's payoff. Each layer exists to solve a problem the layer below *cannot*:

```
LAYER            PROBLEM IT SOLVES          PRIMITIVE           FOLDER
────────────────────────────────────────────────────────────────────────────────
Identity         "what subject am I?"      sub / SA / CN       00 / 06
────────────────────────────────────────────────────────────────────────────────
Authn (passwords "prove the human")       salted KDF          01
 "who typed it")                                                 bcrypt/argon2
────────────────────────────────────────────────────────────────────────────────
Authn (machine)  "prove the service"      cert + mTLS         06
 "who am I, no user"                                             X.509 / workload
────────────────────────────────────────────────────────────────────────────────
Authn (delegated) "prove the RO, once"    signed JWT /        04 / 05
 "so I don't ask again"                             OAuth code→token
────────────────────────────────────────────────────────────────────────────────
Authz            "allowed?"               RBAC / scope /      05 / 06
                                             claim → policy
────────────────────────────────────────────────────────────────────────────────
Confidentiality  "hide the bytes"         AES (sym)           02
 "only the holder reads"                                RSA/ECC (asym)  03
────────────────────────────────────────────────────────────────────────────────
Integrity        "these bytes are whole"  HMAC / SHA / sign   01 / 03
                                             / sig
────────────────────────────────────────────────────────────────────────────────
Key custody      "where do the keys live & how do I rotate" KMS/HSM/envelope 07
```

**Two things to say out loud:**

- **The bottom three rows (confidentiality / integrity / key custody) are cryptography.** They don't care who anyone is.
- **The top four rows (identity / the three authn flavors / authz) are protocols.** They are *built on* the crypto, not the other way round.

This is why the reading order is 00 → 01 → 02 → 03 (build the primitives) → 04 → 05 → 06 (the protocols) → 07 (custody) → 08 (assembly). **You cannot reason about a JWT (04) without understanding that its security is an asymmetric signature (03) and that its claims are just *data the signature protects* (01's integrity).**

---

## Symmetric vs. asymmetric — the fork in the road

One question 02/03 will keep returning to, so name it now:

- **Symmetric** (AES, 02): one key does both directions. *Cheap, fast, small keys.* Problem: **how do two parties that never met agree on the same secret without an eavesdropper seeing it?** (Answer: a key-exchange / key-distribution protocol — out of scope here, but it's *the* reason asymmetric exists.)
- **Asymmetric** (RSA/ECC, 03): a **public/private** pair. Public encrypts / verifies, private decrypts / signs. *Slower, big keys* — but **no shared secret to exchange.** One key can be public.

> **The signing asymmetry (the exact sentence a panel wants):** asymmetric beats symmetric **for signing** because **many parties can verify with the public key, but only the one holding the private key can sign.** You can hand the public key to the entire internet; no one can forge your token. Symmetric signing (HMAC, 01) is fast but **the key is shared with every verifier** — leak it once and every verifier's trust collapses. JWTs are asymmetric-signed (04) *for exactly this reason.*

> **The encryption asymmetry:** asymmetric beats symmetric **for key distribution** — I encrypt *to your public key*, only *your private key* decrypts. But asymmetric encryption is **slow and short-layload** (RSA can't encrypt a 4KB blob efficiently). So real systems do **hybrid**: asymmetric to exchange a *fresh symmetric session key*, then symmetric to encrypt the bulk. TLS does this. Envelope encryption (07) does this. **This "hybrid" pattern is the single most-repeated structure in the whole project.**

---

## Fit-to-project: where this mental model gets used

This project builds **one service** (08) that touches *every* row of the stack:

- **Identity + Authn (human):** a user logs in with a **salted, stretched password** (01) — that's the `sub` and the proof.
- **Authn (delegated):** the service mints a **short access JWT + a rotating refresh JWT** (04), and exposes a **JWKS** so consumers verify locally (04/07).
- **Authn (machine):** service-to-service calls use **mTLS with per-pod workload identity** (06).
- **Authz:** a **scope/claim** on the access token + an **RBAC role** for the service account (05/06).
- **Confidentiality:** a sensitive DB field is **AES-GCM encrypted under a KMS envelope key** (02/07).
- **Integrity:** the JWT signature (03) and an **HMAC** where a shared secret is genuinely all you have (01).
- **Key custody:** everything above is held and rotated by a **KMS/HSM + secret manager** (07).

**The capstone is this diagram drawn as a system.** Each decision in 08 maps to exactly one row above.

---

## Thresholds / tradeoffs that govern *this* project

| Decision | Guidance |
|---|---|
| Symmetric vs. asymmetric | Symmetric for bulk *data* (02); asymmetric for *signing + key distribution* (03); hybrid (envelope) when you need both (07) |
| Where Authz lives | In a **claim** on the token (05) if the RS must decide locally; in **RBAC on the resource** (06) if the resource owns policy. Don't put both and call it one. |
| Bearer blast radius | The smaller `exp`, the smaller the damage. Access ≤ 15 min (04). Refresh is the long one — rotate it (04). |
| "Proof without a call" vs. "proof with a call" | **Stateless** (verify JWKS locally, 04) = fast + no revocation; **stateful** (introspect the IdP, 05) = revocable + slow. Pick per endpoint, not per system. |

---

## The one diagram, drawn for the wall

```
────────────────────────────────────────────────────────────────────────────────
   HUMAN            │                THE PROOF                  │   MACHINE
 ┌────────┐         │                                           │         ┌────────┐
 │ user   │─passwd──►│  Authn:  KDF(01) ─► subject              │──mTLS──► │  2nd  │
 │        │  (salt+  │           cert (03) ─► subject (SA 06)   │   X.509   │ svc   │
 └───┬────┘   stretch)│                                           │          └───┬──┘
     │               │  Authz:  RBAC / scope / claim            │             │
────────────────────────────────────────────────────────────────────────────────
     │                                                                             │
     │  IdP (Keycloak)                                                            │
     │  ┌──────────────┐   sign (private key, 03)    verify (public key, JWKS 04)  │
────────────────────────────────────────────────────────────────────────────────
     │  │  code→token  │        access JWT (04)      ◄──────────────               │
     │  └──────────────┘        refresh JWT (04)                                   │
     │                                                                             │
     │  DATA:  sensitive field ──AES-GCM(02)──►  KMS envelope key (07)           │
────────────────────────────────────────────────────────────────────────────────
```

Keep this picture. Every command in 08 points at one box.

---

## Failure modes to deliberately cause (from the model)

These are the *conceptual* failures; each has a concrete drill in its folder.

1. **Confuse integrity with secrecy.** Read a JWT's payload and assume it's private. It's not — only its *signature* is the protection. Drill in 04.
2. **Let one secret hold the world.** A shared HMAC key (01) as the only thing standing between you and every verifier. Leak it, all trust dies. Prefer asymmetric signing.
3. **Forever credentials.** A token / service-account cert with no `exp`. Blast radius = your whole system. Drill: make everything have a lifetime (04/06).
4. **Authz in the wrong place.** Encode the whole permission model in a token claim (05) so the resource can't override it — or put it only in RBAC (06) so the token is a rubber stamp. Pick one owner.
5. **The missing leg.** A "token flow" where the Client talks to the RS but the RO was never asked. That's an **authorization-code flow without consent** — the whole point of OAuth is the RO's yes.

---

## The L5/L6 lens: what panels probe on *this* folder

| Panel probe | The refute they're hunting | The artifact that *stops* it |
|---|---|---|
| "Explain what a token *is*." | "You'll call it authentication." | "A token is **bearer evidence of authn** — possession implies the claim, and a signature makes it locally verifiable. The signature protects **integrity**, not secrecy. That's why we keep `exp` short." |
| "Symmetric or asymmetric? Why?" | "You'll say 'asymmetric is more secure' with no mechanism." | "Symmetric: one shared key, fast, but **distribution is the problem** and one leak kills all verifiers. Asymmetric: **many verify with public, only one signs with private** — that's why JWTs are asymmetric. For bulk data I go hybrid (envelope, 07): asymmetric to move a fresh symmetric key, symmetric to encrypt the payload." |
| "Identity vs. authn vs. authz." | "You'll treat them as synonyms." | "Identity = the `sub` (noun). Authn = I confirmed this `sub` (password KDF, cert, or signed token). Authz = can this `sub` do *this action on this resource* (RBAC/scope). You can have any two without the third." |
| "Where does authorization live in your system?" | "You'll say 'in the token.'" | "The token carries a **claim** the RS *can* consult; the RBAC **role** on the resource is the policy that *enforces*. The claim is data; the policy is the decision. I don't let a claim override the resource's policy." |

> **The meta-skill:** the mental model exists so that when a panel says "your system has X," you can answer "X is **<row of the stack>**, and it depends on **<these two rows>**, which I sized in 0<…>." If you can't place a term on the diagram, you don't know it.

---

## Cross-refs (name the sibling doc when two topics interact)

- **What a token is / bearer blast radius** → `04-jwt` (claims, `exp`, rotation, revocation) and `05-oauth-oidc` (the flow that mints it).
- **Symmetric vs. asymmetric fork** → `02-symmetric-encryption`, `03-asymmetric-encryption`; the hybrid/envelope resolution → `07-key-management`.
- **Authn for machines** → `06-service-accounts` (SA, workload identity, mTLS).
- **Where the keys live + rotation** → `07-key-management` (KMS/HSM, envelope, drills).
- **All of it assembled** → `08-capstone`.

---

## Exit criteria for this folder

- [ ] You can define **identity / authn / authz** as three separate questions and give one artifact for each.
- [ ] You can say, unaided: "a token is **bearer evidence of authentication**; its **signature** protects **integrity, not secrecy**."
- [ ] You can draw the **three-legged dance** and name all four actors (RO / Client / IdP / RS).
- [ ] You can state **why asymmetric beats symmetric for *signing*** (many verifiers, one signer) and **for *key distribution*** (no shared secret to leak).
- [ ] You can place every folder of this project (01–08) on one row of the stack diagram.

Next: `01-hashing` — the first primitive, and the one passwords depend on.
