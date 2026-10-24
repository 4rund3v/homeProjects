# 01 — I/O-bound vs CPU-bound: the decision that picks your concurrency model

## The question the whole repo is about

> "I want to hash all the files in a directory, find duplicates, list full paths. Is this a good asyncio use case?"

The answer is **both and neither**, and the *reason* is the single most important concept in asyncio:

| Work | Type | Where it runs | Does `asyncio` help? |
|---|---|---|---|
| `open` / `read` a file, a *syscall* / *page-cache* miss | **I/O-bound** | on the loop, *yielding* while the kernel waits | **Yes** — the loop runs *other* coroutines during the wait |
| `hashlib.sha256(data)` over a *large* buffer | **CPU-bound** | on the loop, *blocking* the whole loop | **No** — it runs *alone*, and *freezes* everything else |

The **rule**: **concurrency helps when the *time* is spent *waiting*. It does *not* help when the *time* is spent *computing*.**

## Why a CPU loop *blocks* the loop

The event loop is *one* thread. A coroutine that *computes* for 100 ms does not *yield* — there is no `await` *inside* a tight `hashlib` loop. For those 100 ms, the loop is *stuck* on *that* coroutine, and *no* other coroutine can run. The "concurrency" *collapses to serial* for the duration of the CPU burst.

So a "fully-async" hash that *awaits* a per-chunk `hashlib` call is **worse** than a serial hash: you *pay* the async overhead *and* you *block* the loop on every chunk. **Never make CPU work `await`-able on the loop.** This is the exact mistake your instinct is circling; the repo's CLAUDE.md codifies it as *Rule 2* of the anti-goals.

## The three *correct* answers for CPU work

For the hashing half, you have exactly three *correct* choices (and one wrong one):

1. **Wrong:** `await` a *coroutine* that does the hash on the loop. *Blocks* the loop. Never.
2. **Cheap blip:** `await asyncio.to_thread(hash_file, path)`. Runs the hash in a *thread* (the `ThreadPoolExecutor`), so the loop is free. Good when the hash is *short* or you have *many small* files. *Cost:* a *thread* still cannot run *two* hashes at *once* across *all* cores for *one* file, and you get GIL *contention* between *threads*.
3. **Sustained CPU:** `await` a *process* call via `ProcessPoolExecutor` (through a small `async` wrapper). Each hash runs in a *real* *process* → *all* cores, no GIL. *Cost:* *pickling* the bytes across the process boundary.

For *large* files and *many* of them, **option 3** is the real answer, and *option 2* is the *fallback* when files are small. `docs/03` is the bridge to option 3.

## The *I/O* half is where asyncio *really* shines

Reading *many* files *concurrently* — the *syscalls* wait on *disk* (or *page cache*) — is the *textbook* asyncio case. One coroutine *per file*, *gathered*, and the loop *multiplexes* the *waits*. *This* is the "is my hash tool a good asyncio use?" **yes** part: the *reading* of thousands of files is *massively* I/O-bound.

But here is the *subtlety* a "really good at asyncio" person knows: **on Linux, `asyncio`'s default I/O loop is *good* at *network* and *timers*, but *blocking* *file* I/O (`open`/`read` on a *regular file*) does *not* *natively* yield to the loop.** The loop *cannot* `epoll` on a *regular file's* read. So "read 1000 files concurrently" does *not* get the clean *epoll* win that "fetch 1000 URLs" does. You handle it one of two ways:

- **`asyncio.to_thread`** (a *thread pool*) for the *file reads* — the *simplest* correct answer. The reads *run* in *threads*; the loop is free.
- **A real async filesystem** (`aiofiles`, or `os` *in* a thread, or *Linux* `io_uring` via `uvloop`/a *C* backend) — the *faster* answer, at the *cost* of a *dependency*.

For the *learning* tool, **`to_thread` for the I/O** is the *right* *first* choice: it is *correct*, it *demonstrates* the I/O/CPU split *cleanly*, and it does *not* pretend that `open()` on a regular file is *epoll-able*. `docs/05` (uv) is where you would reach for a *faster* *backend* if the *I/O* *became* the *bottleneck*.

## The *decision* you will *make* in the *dup tool*

```
for each file in the tree:
    read the bytes      →  I/O  →  to_thread (thread pool)   [docs/05 for a faster I/O]
    hash the bytes      →  CPU  →  ProcessPool (all cores)    [docs/03]
    group by hash       →  CPU  →  serial (dict) — trivial, no concurrency needed
```

*The read* and *the hash* are *deliberately* *different* *mechanisms*, *because* they are *different* *kinds* of work. *Conflating* them ("just `await` everything") is the *exact* failure this repo exists to prevent.

## The *measured* *proof*

`examples/ex1-io-vs-cpu.py` does the *A/B*:

- **I/O case:** 1000 × `await asyncio.to_thread(read_small_file)` — *measured* wall time.
- **CPU-on-loop:** 1000 × a *tight* `hashlib` *loop* *on the loop* — *measured* wall time. *(This is the one you should **never** do; the measurement is the *demonstrable* reason.)*
- **CPU-on-pool:** 1000 × hash *in* a *ProcessPool* — *measured* wall time.

The *three* numbers, side by side, are the *entire* doc in *one* screen. The *pool* number *beats* the *on-loop* number by *the number of cores* (the GIL is *gone*). The *on-loop* number is *the worst* of the three, *worse* than *serial*, *because* it *blocks* *and* *pays* the *async* *overhead*.

## The *one-line* *summary* a *senior* *engineer* *gives*

> "The tool reads files (I/O) and hashes them (CPU). I run the *reads* with `asyncio` + a *thread pool*, and the *hashes* with a *process pool*, because CPU work must *leave* the loop. I *measure* all three. I *do not* `await` the hash."

That *one line* is the *goal* of this whole folder. `docs/02` shows *how to orchestrate* the I/O; `docs/03` shows *how to bridge* the CPU; `docs/04` shows the *whole tool*.
