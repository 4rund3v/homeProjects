# 06 — Service Accounts, Workload Identity, and Service-to-Service mTLS

**Folder:** `06-service-accounts/`

Everything so far assumed a *human* who types a password or *consents* in a browser. **A service has no human.** It can't "log in." So it needs **its own identity that is a *machine*, not a person** — that's a *service account*. The two questions a panel will ask: **(1) why should an app *ever* authenticate with a user's credentials, and (2) how does a *machine* prove *who it is* without a password.** The answer to (2) is **workload identity + mTLS**, and it reuses the *entire* asymmetric/cert stack from 03 — just pointed at *the machine* instead of *the person*.

---

## Teach first: the *failure that makes service accounts *exist — "why not *a user cred?"

A *machine* that calls an API **on a user's behalf** has *two* identities in play:
- **The user's* identity (who *owns* the resource, *who consented) — *the OAuth scope (05), a human token.
- **The machine's* identity (which service is *actually making the call) — *a service *account, a *machine* token.

**The *failure that makes service accounts *exist:** a machine *holds* a long-lived *user* credential (a personal access *token, a *user's API *key) to call an API on *the user's behalf. *Now:*
- *The user's *token *outlives the user's session* (a *compromised *service can *keep calling for *days).
- *You can't audit *"who ran this"* — *the *call is *the user's, not the service's.
- *The *user's permissions are *inherited wholesale* (a *token with *admin scope, *held by a service that only needed *read).

**Service accounts *exist to *separate the *machine's identity from *the user's:** *the *machine authenticates as *itself* (a *workload identity), *and *the *user's consent / *the user's data is *attached as a *claimed context, *not *as the *credential. **The L5 one-liner: **"a *machine shouldn't *borrow a human's* token; *it should *have its own, *scoped, *machine identity."**

> ***The threshold: *never hand a service a *long-lived, *high-privilege user* credential.** If a service *needs* access to *a user's data, *the pattern is: ***the user's consent + scope (a short, *bound OAuth grant, 05) + the *service's own workload identity (mTLS/SAS), *and the *resource checks *both.* *The service's *creds are the *short, scoped, machine-bound ones, *never the user's long ones.**

---

## The three *kinds* of "service account" (name which one you mean)

| Type | *What it *is* | *How it *proves who it is* | *The *sibling doc* |
|---|---|---|---|
| *k8s ServiceAccount* | *a *k8s object that *a Pod *runs as; *the Pod gets a *token mounted / projected *into it* | ***Projected* ***JWT** (the k8s API *issues it, *signed by the k8s CA, *aud = the k8s API), *or a SAS token | 06 (this) + *RBAC |
| **Workload identity* | the generic "this workload *is X" *identity, *independent of the runtime* (SPIFFE/SPIRE, *a *cloud *SA) | **a *short-lived cert *signed by *a workload CA* (the *workload *identity *is a cert, 03), *or a *short-lived *SAS JWT* | 06 + `03` |
| **Cloud SA* (GCP/AWS/Azure) | *a *cloud IAM principal that a machine *impersonates (a GCP SA, an AWS *role) | ***a *short-lived cloud *cred** (a GCP *workload-identity-federation *token, an AWS *AssumeRole *STS *token) | `06` + *07 |

> ***The *mechanism that ties *all three together (the *single abstraction):* ***"a *short-lived credential, *signed by a CA/IdP, *audience-bound to the resource, *rotated on a schedule."** *That one sentence is *k8s's projected *SA *token, *SPIFFE's *workload cert, *and GCP's federated *token *all at once.* *The *difference is *who the CA/IdP is *and *what runtime issues it.*

---

## k8s ServiceAccounts, in *concrete detail

**A k8s *ServiceAccount (SA)** is *a k8s object that *a Pod *runs as. *It has *no password — *its *credential is a *projected* ***JWT the k8s API server mints and projects into the Pod** *on a *schedule.

**The two *SA *token shapes (the *ones a panel will ask which you use):**

| | ***Legacy** (a *mounted *file, *a bearer token in *a Secret) | ***Projected / *bound** (a *bound token) |
|---|---|---|
| *What it is* | a long-lived SA *token *in a k8s *Secret, *mounted as a file* | a short-lived ***JWT, *audience-bound, *projected into the Pod on schedule* |
| *Lifetime* | ***long-lived** (a *credential *that lives *until you delete the Secret) | ***short** (e.g. *1h, *rotated by the *kubelet) |
| ***aud** | *none / *loose* | ***audience-bound** (the token says *"I'm valid for *the k8s API, not *anything else") |
| ***Rotation** | *manual (delete the Secret) | ***automatic** (the *kubelet *re-projects) |
| *Verdict* | *The *insecure one; *a leaked *mount file = *the whole SA* | ***The default; *a *short, *aud-bound, rotating credential |

> ***The threshold (the *exact* k8s decision): ***always use projected / *bound SA tokens** (the *short-lived, *aud-bound, *auto-rotating ones), ***never legacy mounted-Secret tokens** (the *long-lived, *leakable ones). **This is the "a *machine's *credential is *short + *scoped + *rotating" rule, *applied to k8s.

**The commands that *make this *real (a senior *runs these, not reads about them):**

```bash
# the SA + a bound token, aud-bound to the k8s API
$ kubectl create serviceaccount web-svc -n shop
$ kubectl create token web-svc -n shop --audience=https://kubernetes.default --duration=1h
#    → a short-lived, audience-bound JWT (the "bound token"; the capstone's SA path)

# who this pod runs as (the workload identity in-cluster)
$ kubectl get pod web-0 -n shop -o jsonpath='{.spec.serviceAccountName}'

# what the SA can do (RBAC — the AUTHZ row, 00): a Role + a RoleBinding
$ kubectl get role,rolebinding -n shop
#    → the SA's allowed verbs/resources = its permissions (RBAC, not identity)
```

**The RBAC *split (00's *identity-vs-authz *row, *made concrete in k8s):**
- ***Identity** = *the SA (`web-svc`), *proven by the *bound token.
- ***Authn** = *the k8s API *verifying the *token's signature (the k8s CA).
- ***Authz** = *the **Role**/**RoleBinding** *that says `web-svc can get pods in shop`. **The *token proves *who; the *RBAC *policy decides *what. *They are different layers (00).

---

## Workload identity + mTLS service-to-service: the *machine's *cert

This is **03's cert/PKI *applied to a *workload**, not *a person:

- ***Every workload gets a short-lived cert** *signed by **the *workload CA** (SPIRE, *a k8s *mesh CA, *the cloud CA). *The cert's *CN/SAN = *the workload's identity (`web-svc in shop`, *the SPIFFE ID `spiffe://…/web-svc`).
- ***Service A → Service B** = **mutual TLS**: *each presents *its cert, *each verifies *the other's cert *against *the CA they trust (03's chain). *The *identity is in the *cert's SAN, *not in *a username.
- ***The per-pod issuance (the *capstone's command):** *a *cert issued per *pod* *by the CA, *short-lived, *rotated by the *mesh/CA on a *schedule.

**The mTLS *sequence (the *exact thing a panel will make you *walk through):**

```
SvcA [cert: A] ──ClientHello, *cert A ──► SvcB [cert: B]
SvcB *verifies A against the CA they both trust (A's CN = "web-svc")
SvcB *verifies its own cert B
TLS tunnel *up (AES-GCM, 02's *symmetric bulk over the *asymmetric handshake, 03)
Now SvcB knows: "the caller is *web-svc" (a *machine identity, *not a user)
```

> ***The threshold (what mTLS *buys you over plain TLS):* ***plain TLS** = *the caller is "someone *who reached you *over TLS." **mTLS** = *the caller is "the *workload named X, *proven by *a cert signed by *the CA." **mTLS is *identity, not just *encryption.* Without it, *a compromised *service can *call any *peer as *whatever identity the peer trusts (00's "a *compromised Pod can be 'whoever' on the *wire").

**Why mTLS *pairs with PKCE (05, the cross-ref):* *PKCE *proves a public *browser client's code is *the right one; *mTLS *proves a *workload's *cert is *the right one. *They're *the two "prove it's the *right party" mechanisms, *for *the two *different callers (a *browser *vs a *workload). **They don't *compete — *they *cover *different hops.**

---

## Cloud service accounts (GCP/AWS): the *other *two

The *same "short, *scoped, *machine" principle, *three *cloud shapes:

- ***GCP:** a ***GCP service account** (an *IAM principal). *A *workload *gets a *short-lived **workload-identity-federation token** (a *JWT *signed by an *external IdP, *exchanged for *GCP creds *for a bounded time). *The workload *calls GCP APIs as *the SA, *scoped.
- ***AWS:** a ***IAM role assumed via STS** — *a workload calls **AssumeRole** and gets **short-lived temporary credentials** (*an access key + *a *secret + *a session token, *all *bounded, *all scoped by the *role's policy). *This is *the "a *machine gets *temporary *cloud creds, *not a *long-lived user access key."
- ***Azure:** a ***managed identity** (the *workload's *identity is the *VM/Service-App, *no client *secret, *a *short-lived token from *the identity service).

> ***The unifying threshold (the *one sentence):* ***"a *workload's cloud access is a short-lived, scope-bound, *temporary credential, *issued by the *cloud's IdP, *audience-bound to the *specific API + *the specific resource — *never a long-lived user IAM *key.** This is the *AWS STS / *GCP federation / *Azure managed-identity *rule, *all one principle.

---

## Fit-to-project: where this is the capstone's *machine story

The capstone (08) has *two callers:
1. ***The user** → *a human (01's password, 05's OAuth). *A **service account *is the *user's *identity, not the *machine's.**
2. ***The second service** → *a machine (this *doc). ***It authenticates as itself** via **a k8s SA bound token (06)** *or **a workload mTLS cert (06)** *or **a cloud SA federation token (06).**

**The *one decision that *separates the two (the *panel question "why *mTLS between *services but *OAuth between *a user and *a service?"):**
- ***User → *service: OAuth (05) — *the *user's consent + *a scoped grant + *a *human identity.**
- ***Service → *service: mTLS / *a workload SA (06) — *the *machine's *identity + *a machine scope (no human, *no consent.

> ***The *threshold that *ties it together (the *one that *answers "why *should apps use these *instead of user creds"):* ***the service's *credential is machine-bound + short + *audience-bound to the *specific peer (mTLS cert) or the *specific API (cloud federation token). It's *NOT a user's long-lived token.** *That *separation is *what lets *the *resource (06's RBAC / *05's scope check) *decide "I'll serve *a *call from *web-svc, *not from *a *user who's *logging in."

---

## Thresholds and tradeoffs summary

| Decision | Guidance |
|---|---|
| *A service's *credential | ***a machine workload identity** (k8s SA / *workload cert / *cloud SA), ***never a user's long-lived token.** |
| k8s SA token | ***projected / *bound** (short, *aud-bound, *auto-rotating). ***Never legacy mounted-Secret** (long, *leakable). |
| *S2S transport | **mTLS** (identity + *encryption), ***not plain TLS** (encryption only). |
| *Cert lifetime | ***short + rotating** (the *workload CA *issues per-pod, *rotates on schedule. |
| *Cloud SA | ***a short-lived, scope-bound, *temporary credential** (GCP federation / AWS STS / *Azure managed identity), ***never a long-lived user IAM *key. |
| *The RBAC *split | ***identity (the SA/cert) proves *who; *RBAC/scope decides *what.** *They're different layers (00. |

---

## Failure modes you must deliberately cause

1. ***A service using *a user's long-lived token (the *whole reason *service accounts *exist):** *a service *holds a personal access *token with *admin scope. *The *user's session ends, *the service *still calls for *days; *an audit can't tell *who ran *what. *The *fix: *the *service *authenticates as *itself (SA / *workload cert), *the *user's consent/scope is *attached as *a claimed context, *not the *credential.
2. ***A legacy mounted-Secret SA token (the *k8s long-lived leak):* *the SA token *is a file in the Pod, *long-lived. *A *sloppy read (a `cat` in a *debug sidecar, *a log that *echoes *the mount) *leaks the *whole SA. *The *fix: *projected / *bound tokens (short, *rotating, *aud-bound).
3. ***Plain TLS *instead of mTLS (the "who is *this caller" hole):** *S2S *over plain TLS. *A *compromised service *can call any peer as *whatever identity the peer trusts (00's "a compromised *Pod can be 'whoever'). *The *fix: *mTLS, *each side *presents a CA-signed cert, *the identity is in the *SAN.
4. ***A wrong-identity S2S call (the *aud / *SAN mismatch):** *service A presents *a cert whose CN = `other-svc` *but calls as `web-svc`. *The *peer's CA-chain check *must reject it (the *cert *doesn't say `web-svc`). **The *drill: hit a service with the wrong-identity cert → the mTLS handshake *fails on the *SAN mismatch.**
5. ***A long-lived cloud user *key *in a *service (the *cloud *version of #1):** *a *service holds an AWS *IAM *user access *key. *The *fix: *AssumeRole *via STS (a *short, *scoped, *temporary credential), *the "never a *long-lived user *key" rule.
6. ***A workload cert *that outlives *the rotation (the *stale-cert leak):** *a per-pod cert *that the CA *rotated *but the Pod *still holds the *old one. *A *stale cert *is a *leaked identity. *The *fix: *the mesh/CA *force-rotates + *the *short lifetime means *a *stale cert *expires anyway (03's leaf-lifetime rule).

---

## The L5/L6 lens: what panels probe

| Panel probe | The refute they're hunting | The artifact that *stops* it |
|---|---|---|
| "***Why *should a service use *its own *credential, *not the user's?**" | "You'll say 'it's cleaner.' *No *the *three *failures." | ***Three: (1) *a *user token *outlives the session** (a *compromised *service keeps calling *for days), **(2) *audit can't tell *who ran it** (the *call is the *user's), **(3) *permission inheritance** (a *service gets the *user's full scope). *The *fix: *a *machine-bound, *short, *aud-bound service identity, *the user's *scope attached as *a *claim, *not the *credential.* |
| "**What is a *workload identity, *concretely?**" | "You'll say 'a service account.' *No the *abstraction." | ***"a short-lived credential, *signed by a CA/IdP, *audience-bound to the resource, *rotated on a schedule."** *That *sentence is *the k8s *bound SA *token, *SPIFFE's *workload cert, *and GCP's *federated token *all at once. *I pick the *one *that matches my runtime (k8s → *bound SA / *workload cert; *cloud → *the cloud SA / *federation). |
| "***k8s *SA *token — which *one do you use?**" | "You'll say 'a token.' *No *the *two *kinds." | ***Project / *bound** (short, *aud-bound, *auto-rotating, *the default) ***vs legacy mounted-Secret** (long, *leakable, *never). *I use `kubectl create token` with *an audience + a *duration — *the bound token. *The *kubelet re-projects *it; *the *mount file *leaks the *whole SA *if it's the *legacy one. |
| "***Plain TLS or *mTLS *between services? *Why *mTLS?**" | "You'll say 'it's *more secure.' *No *the identity *difference." | ***Plain TLS = *the caller is 'someone who reached you over TLS.** ***mTLS = *the caller is 'the *workload named X, *proven by a CA-signed cert** (the *identity in the *SAN, not a username). *I need *the *identity (a *compromised *Pod can't *spoof another service), *so *mTLS. *Plain TLS *only encrypts." |

> ***The meta-skill:*** ***for *any "is *this *machine *authed *right?", *run the *4-part check:*** ***Is its *credential machine-bound (not a user's)? / *short + *audience-bound? / *rotated on a *schedule? / *does the *resource check *the *RBAC/scope (authz) *separately from *the identity (authn)?*** ***If you can't produce *all four, *you've been *treating a *service's *token *as if it were *a user's.**

---

## Cross-refs (two topics interacting → name the sibling)

- ***The k8s SA / RBAC** → `05-oauth-oidc` (the *machine's *client-creds *flow is *the *OAuth *version of this) *and `07` (the *CA that *signs the *workload certs is *a *key in the HSM).
- ***The mTLS *cert chain** → `03-asymmetric-encryption` (the *root CA / *leaf / *rotation hierarchy, *the `keyUsage` + *`CA:FALSE` *that make a *workload leaf *the right *kind of cert).
- ***The cloud SA / *STS** → `07` (the *temporary *cloud creds *are *a *short-lived, *scoped secret *held by the *secret manager).
- ***PKCE + mTLS (05's *two "prove it's the *right party" mechanisms)** → `05` (PKCE for *a browser client, *mTLS for *a workload, *different hops).
- ***The "machine *instead of *a user" *decision** → `08-capstone` (the *second service's *identity in the *runbook).

---

## Exit criteria for this folder

- [ ] You can ***state the *three reasons** *a service *shouldn't use *a user's long-lived token (outlives session / *no audit / *permission inheritance).
- [ ] You can ***give the *one-sentence *workload-identity abstraction** ("short, *CA-signed, *aud-bound, *rotating credential") *and *map it to k8s SA / *workload cert / *cloud SA.
- [ ] You can ***distinguish k8s *bound vs legacy SA tokens** *and *say which you *use (bound, *always).
- [ ] You can ***explain *why mTLS, not plain TLS** (identity *in the SAN vs *just encryption), *and *hit a service *with the wrong-identity cert (the *SAN-mismatch drill).
- [ ] You can ***name the cloud versions* (GCP *federation / AWS STS / *Azure managed identity) *and *say the *one *principle they *share (short, *scoped, *temporary, *never a *long-lived user *key).
- [ ] You can ***separate identity from *authz in k8s** (the SA proves *who, the *RBAC Role *decides *what).

Next: `07-key-management` — *who *keeps all *these keys (the *signing key, *the CA, *the *DEK/KEK), and *how you *rotate them *without dropping *in-flight traffic.
