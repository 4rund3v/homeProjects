# NGINX Architecture — Master, Workers, and the Event Loop

> Why nginx handles 10,000 concurrent connections in a few hundred megabytes, why a
> reload drops nothing, and how that differs from Apache's threads and Go's goroutines.
> Mechanism first, then the config tree, then the interview answer.

---

## 1. The process model

```
                          ┌──────────────────────────────┐
                          │        MASTER PROCESS         │
                          │  (runs as root; does NO I/O)  │
                          │                               │
                          │  • parses nginx.conf          │
                          │  • binds :80 / :443           │
                          │  • opens log files            │
                          │  • forks workers              │
                          │  • handles signals            │
                          │      (reload, shutdown, ...)  │
                          └───────────────┬──────────────┘
                                          │ fork × N
              ┌───────────────┬───────────┼───────────┬───────────────┐
              ▼               ▼           ▼           ▼               ▼
        ┌──────────┐    ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ worker 1 │    │ worker 2 │ │ worker 3 │ │ worker 4 │ │   ...    │
        │ (unpriv) │    │ (unpriv) │ │ (unpriv) │ │ (unpriv) │ │          │
        └────┬─────┘    └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
             │               │           │             │            │
             └───────────────┴───────────┴─────────────┴────────────┘
                             │
              all workers share the SAME listening sockets
              (inherited from master — the kernel load-balances
               new connections across them)
```

**The division of labor is the whole design:**

- **Master** does privileged, one-time work (bind port 443, read secrets) then mostly
  sleeps. It re-execs on signals.
- **Workers** do all the actual network I/O, as an unprivileged user. They never
  re-read the config.

```
nginx.conf                  RUNTIME (inside a worker)
─────────────               ────────────────────────
static text             →   parsed once at start / reload
directives                   compiled into in-memory structures
server {} blocks             (listen sockets, locations, upstream
upstream {} blocks           peer lists, shared memory zones)
events {} ...
http { ... }
```

**Why this split matters:** a worker never touches the filesystem to "check" config,
and the master is not in the request path. The two can evolve independently — which is
what makes zero-downtime reload possible (§4).

---

## 2. The event loop — the actual reason nginx is fast

Each worker is **single-threaded** and runs an event loop:

```
   ┌─────────────────────────────────────────────────────────────┐
   │                    WORKER EVENT LOOP                        │
   │                                                             │
   │   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌─────────┐ │
   │   │  epoll_  │──►│  handle  │──►│  read /  │──►│  write  │ │
   │   │  wait()  │   │  events  │   │  send    │   │  or     │ │
   │   │          │   │          │   │          │   │  close  │ │
   │   └──────────┘   └──────────┘   └──────────┘   └─────────┘ │
   │        ▲                                            │      │
   │        └────────────────────────────────────────────┘      │
   │                     (never blocks; loops forever)           │
   └─────────────────────────────────────────────────────────────┘

   One worker, one core, tens of thousands of sockets.
   No thread per connection. No blocking calls.
```

### `epoll` in one paragraph

`epoll` is a Linux syscall that says "tell me which of these 10,000 sockets became
readable/writable." The kernel maintains the interest list and returns only the
**ready** ones. The alternative — `select`/`poll` — scans every fd every call, which is
O(connections) per wakeup and collapses past ~1,000 sockets. `epoll` is O(ready
events), so it scales to tens of thousands.

### The three concurrency models compared

```
┌────────────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│                    │  THREAD PER  │   NGINX      │   GO         │   APACHE     │
│                    │  CONNECTION  │   WORKER     │   GOROUTINE  │   (prefork)  │
├────────────────────┼──────────────┼──────────────┼──────────────┼──────────────┐
│ unit of work       │ OS thread    │ event + cb   │ goroutine    │ OS process   │
│ stack / overhead   │ ~8MB         │ ~0 (on heap) │ ~2-8KB, grows│ ~MBs         │
│ 10k idle conns     │ ~80GB stack  │ ~MBs         │ ~tens of MB  │ ~GBs         │
│ scheduling         │ kernel       │ none needed  │ Go runtime   │ kernel       │
│ context switches   │ kernel (μs)  │ none         │ runtime (ns) │ kernel       │
│ CPU-bound work     │ blocks others│ blocks worker│ parallel     │ blocks proc  │
│ gotcha             │ C10K         │ one slow req │ GC pauses   │ memory       │
│                    │              │ stalls a core│              │ explosion    │
└────────────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
```

**The honest comparison:**

- **vs thread-per-connection (Apache prefork, naive Java):** nginx wins on memory and
  context switches by orders of magnitude at high connection counts. A thread's 8MB
  stack × 10k connections is 80GB before any data.
- **vs Go goroutines:** the models are philosophically the same (cheap units + a
  scheduler), but the scheduler differs. nginx's is the **kernel** (`epoll`) and its
  units are *events*, not stacks; Go's is a **userspace runtime** (M:N) and its units
  are *goroutines* with growable stacks. Go is easier to write correct code in; nginx is
  leaner and has no GC. Both demolish thread-per-connection.
- **The cost of nginx's model:** a worker is single-threaded, so a **blocking operation
  stalls every connection on that worker**. One slow upstream that nginx waits on
  synchronously, or a slow disk read, idles a whole core. This is why nginx config is
  full of timeout directives (§`reverse-proxy.md`) and why you set
  `worker_processes auto` (one worker per core).

**CPU-bound work is the wrong tool for nginx.** It proxies, terminates TLS, rate-limits,
and serves files. If you need to compute, that belongs upstream — nginx should never be
where your CPU goes.

---

## 3. The config tree

```
nginx.conf
├── user / worker_processes / pid        ← process-level
├── events { worker_connections ... }    ← per-worker limits
├── http {                               ← the main stage
│   ├── upstream api { server ...; }     ← named backend pool
│   ├── limit_req_zone ...               ← shared memory zones (see rate-limiting.md)
│   ├── log_format ...                   ← how access logs look
│   └── server {                         ← a virtual host
│       ├── listen 443 ssl;
│       ├── server_name api.example.com;
│       ├── location /api/ {             ← matched by URI
│       │   ├── proxy_pass http://api;   ← forward to the upstream
│       │   └── proxy_set_header ...;
│       }
│       └── location / { try_files ...; }
│   }
│ }
```

**Contexts nest and inherit:** a `proxy_read_timeout` set in `http{}` applies to every
`location` below it unless overridden. This is why a stray directive in the wrong block
silently changes behavior everywhere — read the config top-down when debugging.

**`nginx -t`** validates the config without applying it. **Always** run it before a
reload; a syntax error means nginx keeps running the *old* config and you think your
change took effect when it didn't.

```bash
nginx -t          # test only
nginx -s reload   # validate + reload
```

---

## 4. Config reload — why nothing drops

This is the second classic interview answer, and the mechanism is elegant:

```
  TIME ──────────────────────────────────────────────────────────►

  t0   master running, workers W1..W4 hold live connections
       │
  t1   nginx -s reload  →  master receives SIGHUP
       │
  t2   master re-parses nginx.conf
       │   (if it FAILS: abort. old workers keep serving. this is why
       │    a bad config is not an outage.)
       │
  t3   master forks NEW workers W1'..W4' with the new config
       │
       │   ┌──────────────────────────────────────────────┐
       │   │  BOTH generations coexist briefly            │
       │   │                                              │
       │   │  W1  W2  W3  W4    ← OLD: still serving      │
       │   │  W1' W2' W3' W4'   ← NEW: accepting new conns│
       │   └──────────────────────────────────────────────┘
       │
  t4   master sends SHUTDOWN to OLD workers
       │   → they finish in-flight requests, close keepalive
       │     connections, then exit
       │
  t5   only NEW workers remain. Zero dropped connections.
```

**The key insight:** the new workers start and take over *new* connections while the old
ones *drain*. A request that arrived at t2 completes on an old worker under the old
config. Nothing is killed mid-flight.

**What this does NOT cover:** a *new* listen socket, a changed upstream peer list that
in-flight requests depend on, or anything stored in shared memory zones whose key
changed — those can still produce surprises. But the connection-level guarantee is real,
and it's what makes `kubectl rollout restart` and configmap updates safe.

**Corollary:** because reload doesn't drop connections, a broken config change can go
unnoticed if the new workers fail their health checks while old ones serve happily.
Verify the new generation actually took over (see
[`tuning-and-observability.md`](tuning-and-observability.md) §config-debugging).

---

## 5. Upstreams

An `upstream` block names a pool of backend servers so `proxy_pass` can refer to it by
name — that indirection is what makes load balancing, health checks, and keepalive
possible.

```nginx
upstream api {
    # reuse TCP connections to Django — without this, every request
    # pays a fresh TCP handshake to the upstream
    keepalive 32;

    server api-svc:8000 max_fails=3 fail_timeout=10s;
    # in k3s, `api-svc` is the Service DNS name; nginx resolves it
    # ONCE at startup — see the gotcha below
}
```

**The DNS gotcha (critical in k3s):** a variable in `proxy_pass` (e.g. using a variable
or a resolver-dependent name) forces **runtime** resolution and requires a `resolver`
directive. A static `server api-svc:8000;` is resolved **at config load**, and if the
Service's ClusterIP changes, nginx keeps dialing the old IP until reload. In k3s the
ingress controller handles this for you (it watches EndpointSlices and re-renders), but
if you ever write raw nginx config, know that this is the mechanism.

---

## 6. Interview angle

- **"Why does nginx handle high concurrency with low memory?"** — one event loop per
  worker over non-blocking sockets via `epoll`; no thread per connection, so no 8MB
  stacks and no kernel context switching. Contrast with thread-per-connection, where
  10k connections means 10k threads.
- **"How does nginx reload without dropping connections?"** — new workers start
  alongside old; old ones finish in-flight requests and drain keepalives before exit.
  The listening socket is inherited from the master, so both generations accept.
- **"What's the weakness of the event-loop model?"** — a blocking call stalls the whole
  worker. Hence timeouts everywhere, and CPU work belongs upstream.
- **"nginx vs Apache vs Go?"** — thread-per-connection vs event-loop vs
  scheduler-managed goroutines; memory, context switches, and ease of correct code.
- **"Why does the master exist at all?"** — privileged one-time work (bind low ports,
  read secrets) separated from the unprivileged request path; it's also what survives
  and can re-fork workers.

---

## 7. How this shows up here

- The ingress-nginx controller *is* this architecture: a master, workers, a rendered
  config, and reload-on-change — see [`ingress-in-k3s.md`](ingress-in-k3s.md).
- Because workers are single-threaded, every timeout in
  [`reverse-proxy.md`](reverse-proxy.md) is really "don't let one bad upstream stall a
  core."
- `worker_processes auto` on a 4-core node means 4 workers; our API is small enough
  that the edge is never the bottleneck — but the reasoning in
  [`tuning-and-observability.md`](tuning-and-observability.md) still applies if it ever
  is.
- Zero-downtime reload is what makes Helm upgrades and configmap edits safe on a
  single node with no second replica to fail over to.
