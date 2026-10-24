# 04 — What TLS changes, and what you *cannot* see

TLS is the *L6* layer (`traffic-analysis/load-balancing/06-osi-layers`), and it is the *single* biggest *change* to what a *packet* *reveals*. Once a flow is TLS, *half* of the *peel* (`02` step 4) *disappears*. This doc is *that* change, and the *security* consequences.

## The *before/after* of TLS

**Before** TLS (plaintext HTTP on port 80), the parser *reads* the *whole* L7:

```
GET /api/products HTTP/1.1
Host: shop.local
Authorization: Bearer <token>      ← readable, *and a secret leak*
...
```

**After** TLS (port 443), the L7 is *a TLS record*. The parser *sees*:

```
TLS record: type=ApplicationData, length=4096, ...   ← *just* a length, *not* the content
```

*You* *cannot* read the *HTTP request* inside a *TLS* record. The *only* thing you *can* read, *without the key*:

- The **SNI** (*Server Name Indication*), in the *ClientHello*, *before* the handshake. It is the *hostname* the client *intends* to talk to. It is **plaintext** in the *ClientHello* (a *known* *privacy* *leak* — the SNI is *not* encrypted in TLS 1.2; TLS 1.3 *partially* encrypts it).
- The **cipher suite**, the *key-exchange* *algorithm* (the *strength*).
- The *handshake* *structure* (a *ClientHello*, a *ServerHello*, *certificates*, a *finished*).

*That* is the *entirety* of what a *TLS* flow *reveals* to a *capture* that *does not* hold the *key*.

## The *SYN* *flood* is the *security* reason a *parser* must *stop* on *abnormal* handshakes

The *security* *note* in `03`: a *SYN* *flood* is an *attack* where an *attacker* sends *many* *SYN* packets and *never* sends the *ACK*, so the *server* holds *thousands* of *half-open* connections in its *backlog*. The *server's* *backlog* *fills*, and *legitimate* connections *cannot* open.

*The* *packet* *signature* of a *SYN* flood:

```
many flows, all of them:  SYN  →  SYN+ACK  →  (no third ACK)
many *distinct* source IPs (or *spoofed*), all *half-open*
```

The *parser* *reports* the *half-open* *ratio* *per* *source* *IP*. A *source* with *hundreds* of *half-open* flows is the *flood* *signature*. The *lab* boundary (`../Project.md`): *do not* *amplify* the *attack* — the *parser* *observes* it, it does *not* *respond* to it.

*The* *defense* is *not* in the *parser*; it is in the *kernel* (*syncookies*) and the *LB* (*rate* limiting *SYNs*). The *parser's* *job* is to *show* you *it is happening*.

## The *legal* / *capacity* *boundary*, stated *precisely*

The *lab* *rule* (`../Project.md`): *"do not capture traffic not originated by the lab."* The *operational* *meaning*:

- **The *capture* *interface*** is the *boundary*. A *lab* *interface* that only *sees* *lab* *traffic* (an *isolated* *VLAN*, a *dedicated* *switch* *port*) *does not* *violate* the *rule*, *because* *no* *outside* *traffic* *reaches* *it*.
- **The *retention* *limit*** is *capacity*, not *legal*. A *capture* that holds *N* *flows* and *drops* the *oldest* *bounds* *its own* *memory*, so it *cannot* *run* *away*. The *limit* is *a property* of the *capture*, not a *policy* *toggle*.
- **The *payload* *retention*** is *the* *legal* *line*. The *parser* *emits* *flow* *summaries*, *not* *payloads*. Even on a *lab* *interface*, *retaining* *raw* *payloads* is *the* *thing* *that* *could* *leak* *a secret* (an `Authorization` header, a *database* *query*). The *summaries* are *safe*; the *payloads* are *not*.

*The* *one-line* *rule*: **a *parser* *sees* *headers*, *not* *content*. The *headers* are *the* *routing* *of* *a* *request*; the *content* is *the* *request* *itself*. The *lab* *observes* *the* *routing*; it *never* *observes* *the* *request*.**

## Where this shows up in the *lab*

`labs/see-and-dont-see.md` captures a *lab* *interface* that *sees* *both* a *plaintext* HTTP flow *and* a *TLS* flow, *side by side*. You *list*, *per* *flow*, *what* the *parser* *could* *read* and *what* it *could not*:

| Flow | Readable | Not readable |
|---|---|---|
| HTTP/80 | method, path, headers (incl. `Authorization`) | — |
| TLS/443 | SNI, cipher, handshake shape | the HTTP request, the body |

*The* *two* *rows* *together* *are* *the* *whole* *lesson*: *TLS* *is* *the* *boundary* *between* *what* *a* *network* *reveals* *and* *what* *it* *does* *not*.
