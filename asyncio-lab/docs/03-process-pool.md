# 03 — The bridge to a process pool: getting CPU work *off* the loop

`01` said: *the hash is CPU-bound; do not run it on the loop; use a process pool.* This doc is *how*, and *the exact cost* you pay for it.

## Why a *process*, not a *thread*, for the hash

The **GIL** (Global Interpreter Lock) means *CPython threads* cannot *run two* *pure-Python* *CPU* *loops* *at once*. `to_thread` (a *thread*) *helps* *I/O* (the thread *blocks* on a *syscall*, *releasing* the GIL, *so* others run) but *does not help* *a tight* *hash loop* (the GIL is *held* *throughout*). For *a* *CPU* *task*, *the* *only* *way* *to* *use* *all* *cores* *is* *a* *process* (each process *has* *its own* *GIL*).

*So:* **I/O → thread pool (cheap).** **CPU → process pool (correct for the hash).** *Two different pools, two different reasons.* *That* *is* *the* *design.*

## The `ProcessPoolExecutor` + an `async` wrapper

The executor is *synchronous* (`map`/`submit` return *futures* you *block* on). To *use* it *from* *an* *async* *function* *without* *blocking* *the* *loop*, *wrap* *the* *blocking* *call* *in* *`to_thread`*:

```python
from concurrent.futures import ProcessPoolExecutor
import asyncio

_pool = ProcessPoolExecutor(max_workers=8)   # ~cpu count

def _hash_bytes(data: bytes) -> str:
    # runs in a WORKER PROCESS — not on the loop, not blocked by the GIL
    return hashlib.sha256(data).hexdigest()

async def hash_bytes_async(data: bytes) -> str:
    # the ONLY blocking piece is the submit() → run_in_executor handoff,
    # which we push to a thread so the loop stays free
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_pool, _hash_bytes, data)
```

**The crucial detail:** `loop.run_in_executor(_pool, _hash_bytes, data)` *does not block the loop*. It *hands* the *call* to the *pool*, *returns* a *future*, and *`await`s* it. *While* the *worker process* *computes*, *the* *loop* *runs* *other* *coroutines*. *The* *CPU work* *is* *physically* *on* *other* *processes*. *This* is *the entire* *bridge.*

## The *cost* you pay: *pickling* across the process boundary

`run_in_executor(_pool, _hash_bytes, data)` *pickles* `data` (the *bytes*) and *sends* it to the *worker*, *then* pickles the *result* back. For a *large file*, *that* *copy* is *a real cost* (a *second* full read of the bytes *plus* a *serialization*). Two *ways* to *manage* it:

1. **Hash by *path*, not by bytes** — the *worker* *re-reads* *the file itself* (no pickle of the bytes, *only* the *path* *crosses*). *Better* for *large* files.
2. **Accept the pickle** for *small* files — the *path* *is* *cheaper* to *pickle*, and *the* *bytes* *are* *small*.

*For* *the* *dup tool*, **option 1** (the worker *takes a path*, *reads*, *hashes*, *returns the hex digest*) is the *right* choice: *only the path and the result* cross the boundary. *The bytes never pickle.* This is *the* detail that makes the pool *fast*, and it is *exactly* the kind of thing a "really good at asyncio + concurrency" person knows.

## The *chunked* hash, *if* a file is *huge*

SHA-256 *is* *incremental*. For a *multi-GB* file, the *worker* should *not* *read it all at once*. *It* *streams* in *chunks* *and* *updates* *the* *digest*:

```python
def _hash_path(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:          # in the WORKER process
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)               # 1 MiB chunks — bounded memory
    return h.hexdigest()
```

*The* *1 MiB* *chunk* *bounds* *the* *worker's* *memory* *regardless* *of* *file size*. *A* *tool* *that* *`read()`s* *a* *5 GB* *file* *into* *one* *buffer* *is* *the* *anti-pattern*; *the* *streaming* *chunk* *is* *the* *fix*.

## The *two-level* *design*, *end to end*

This is *the whole* *arch* of *the* *dup tool*:

```
                 ┌──────────────────────────  LOOP (1 thread)  ──────────────────────────┐
   walk tree ──► │ to_thread(read)   fan-out (Semaphore)   collect (hash, path)  group   │
                 └──────┬───────────────────┬───────────────────▲─────────────────────────┘
                 I/O    │                    │                  │
                        ▼                    ▼                  │
              THREAD POOL            PROCESS POOL (8 procs)     │
              (file reads,          (hash_path: read+sha256,     │
               blocking syscalls)    one per core, no GIL)      │
                                                     result ─────┘
```

- *The* *loop* *never* *does* *heavy* *work*. *It* *orchestrates*.
- *Threads* *do* *the* *I/O* (the *reads* *block*; *the* *GIL* *is* *released* *during* *the* *syscall*).
- *Processes* *do* *the* *CPU* (the *hash* *runs* *on* *all* *cores*; *no* *GIL* *contention*).
- *The* *grouping* *(dict by hash)* *is* *trivial CPU*, *run serial on the loop* — *no* *concurrency* *needed* *for* *a* *dict update*.

*The* *restraint* (grouping is serial) *is* *as important* *as* *the* *fan-out*. *You* *do not* *add* *concurrency* *where* *it* *does* *not* *help*.

## *The* *measured* *A/B* — *and* *the* *surprise* *that* *keeps* *it* *honest*

`examples/ex3-pool-hash.py` hashes *the same set* of files *three ways*, *timed*:

| Method | Where the hash runs | Expected | What you *actually* see |
|---|---|---|---|
| on the loop | blocking, 1 thread | **slowest** | the anti-pattern (worse than serial) |
| `to_thread` | a thread pool, *releasing the GIL* | ~serial | **often as fast as the pool** (see below) |
| `ProcessPool` | N processes | ~N× serial | **wins on *large* files, *loses* on *small* ones** |

*The nuance a senior engineer must not skip:* **`hashlib` is a C extension and it *releases the GIL* while hashing.** So a *thread* (`to_thread`) hashes in parallel with the loop's other work — the GIL is *not held* through the SHA-256. Consequences:

- **Small files:** `to_thread` is *near-optimal*, and the process pool's *pickling* cost (serializing each buffer across the boundary) makes the pool *slower*. This is what `ex3` prints when N is small — the pool "losing" is *expected*, not a bug.
- **Large / many files:** the pool *wins*: the CPU work dominates the pickling cost, and the pool uses *all* cores.
- **Either way, the on-loop hash is *worst*** — it *blocks* the loop *and* pays async overhead. *That* is the invariant conclusion; the *pool-vs-thread* race is the nuance.

*The honest lesson:* **do not reach for a process pool on reflex.** Measure first. If the *task releases the GIL* (a C library: *hashlib, numpy, compressed io*), *threads are enough and cheaper*. A process pool is for *pure-Python* CPU loops that *hold* the GIL. `ex3` is *the measurement that decides which case you are in*.

## *Where* *this* *lives* *in* *the* *tool*

- `internal/hasher/` = *the* *`_hash_path`* *function* + *the* *`hash_bytes_async`* *wrapper* + *the* *pool*.
- `internal/orchestrator/` = *calls* *`hash_bytes_async`* *per file*, *in* *the* *bounded* *fan-out*.
- `internal/io/` = *the* *`to_thread`* *reads* *that* *feed* *the* *hasher* (or, *option* *1*, *the* *hasher* *reads* *itself*; *pick* *one*, *don't* *read* *twice*).

*The* *one* *consistency* *rule:* *a file is read* *exactly* *once*. *If* *the* *IO module* *reads* *and* *hands bytes* *to* *the* *hasher*, *the* *bytes* *pickle* *across* *the* *process* *boundary* (*option* *2*). *If* *the* *hasher* *takes* *the* *path* *and* *reads* *itself*, *only* *the path* *crosses* (*option* *1*). *The tool uses option 1.* *Do not read a file in two places.*

## *The* *GIL* *footnote* *a* *senior* *engineer* *remembers*

*`ProcessPoolExecutor`* *is* *the* *portable* *answer*. *On* *a* *Python* *build* *without* *the* *GIL* *(*3.13+* *experimental* *`python3.13t`)*, *threads* *can* *run* *two* *CPython* *loops* *at* *once* — *but* *hashlib* *is* *a* *C* *extension* *and* *still* *releases* *the* *GIL* *during* *the* *hash* (so *threads* *would* *work* *too*). *For* *this* *learning* *tool*, *the* *portable* *choice* *is* *the* *process* *pool*; *the* *GIL-free* *variant* *is* *a* *note*, *not* *a* *default*.
