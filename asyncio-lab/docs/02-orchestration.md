# 02 — Orchestrating I/O: `gather`, `TaskGroup`, and backpressure

Now you know *what* to run on the loop (the I/O). This doc is *how to orchestrate* it: *fan out* to *many* files *without* *spawning* *millions of* *coroutines* or *drowning* *a* *thread pool*.

## `asyncio.gather` — the fan-out, in input order

```python
async def process_files(paths):
    results = await asyncio.gather(*(read_file(p) for p in paths))
    return results          # results[i] corresponds to paths[i]
```

**Properties you must know cold:**

- Results come back **in input order**, regardless of completion order. (The *fast* ones finish first; the list is *re-ordered* to match the input.)
- **By default, the first *exception* cancels the rest and propagates.** `gather` is *fail-fast* unless you say otherwise.
- `return_exceptions=True` makes it *collect* the *exception* objects *instead* of *raising* — you *handle* them *per-file*.

*The* *dup tool* *uses* `return_exceptions=True`: one *corrupt/unreadable* file must *not* *cancel* *the* *whole* *scan*. *Collect* the error, *record* it, *continue*.

## `TaskGroup` (3.11+) — the *structured* version

```python
async with asyncio.TaskGroup() as tg:
    for p in paths:
        task = tg.create_task(read_file(p))
    # fall through: the group AWAITS all of them before leaving the block
```

**Why prefer `TaskGroup` over a pile of `create_task` + `gather`:**

- **Structured**: the `async with` *block* *knows* *all* its *tasks*. When you *exit the block*, it *waits* for *all* of them (or *cancels* all of them on an error). No *orphaned* tasks.
- **Error containment**: if *one* task raises, the *group* *cancels* *the* *others* and *raises* — *like* `gather` fail-fast, but the *cancellation* is *automatic* and *scoped* to the block.
- **No *fire-and-forget***: you *cannot* "spawn and forget." The *block* is the *scope*.

For the *dup tool*, `TaskGroup` *plus* a *manual* *error* *catch* (so one bad file doesn't nuke the scan) is the *cleanest*.

## The *danger* you must *avoid*: *unbounded* fan-out

`gather(*100_000 files)` *spawns* **100,000** coroutines *at once*. Each is *cheap* (a coroutine is ~a *few KB* of *state*), but:

- The *thread pool* (`to_thread` uses a *default* of *min(32, cpu+4)*) *cannot* *run* *100k* *reads* *at* *once* — they *queue*. *The queue is unbounded* by *default*, so *memory* *grows* *linearly* *with* *files*.
- *More* *than* *the* *pool* *can* *handle*, *you* *have* *thousands* of *coroutines* *waiting*, *each* *holding* its *own* *file* *handle* / *buffer*.

**The fix is *backpressure*: a *bounded* concurrency limit.** Two idiomatic ways:

### (a) A `Semaphore` cap

```python
cap = asyncio.Semaphore(64)          # at most 64 reads in flight

async def bounded_read(path):
    async with cap:                  # acquire (await) / release (auto on exit)
        return await asyncio.to_thread(read_file, path)

results = await asyncio.gather(*(bounded_read(p) for p in paths))
```

`Semaphore` is the *most common* backpressure primitive. **Pick the number to match the thread pool** (or *a little below*). If the pool is 32 threads, a cap of 64 *doubles* the *queue* *to* *a* *reasonable* *amount*; a cap of *10_000* *is* *the* *same* *as* *no* *cap*.

### (b) A worker pool of N coroutines pulling from a `Queue`

```python
q = asyncio.Queue()
for p in paths: q.put_nowait(p)

async def worker():
    while True:
        p = await q.get()
        try:
            results.append(await asyncio.to_thread(read_file, p))
        finally:
            q.task_done()

await asyncio.gather(*(worker() for _ in range(N)))
await q.join()
```

This is *explicitly* **N workers**, no *unbounded* spawning. It is *more* code but *the* *shape* *you* *reach* *for* when the *work* is *heterogeneous* (different files need different treatment). For the *dup tool*, the *Semaphore* version is *simpler* and *sufficient*; the *Queue* version is the *template* for when you add *per-file* *customization*.

## The *thread* pool is *also* *bounded* — *know* the *number*

`asyncio.to_thread` runs on the loop's **default `ThreadPoolExecutor`**, sized `min(32, os.cpu_count() + 4)`. On a *4-core* box, that's **8 threads**. *Eight* concurrent *file reads*. Everything above 8 *queues*. So:

- Your *Semaphore* cap *should not* *far* *exceed* the *pool* size, or you are *queueing* *into* *the pool* *with* *no* *bound*.
- For *heavy* I/O, **raise the pool**: build your *own* `ThreadPoolExecutor(max_workers=64)` and pass it to `to_thread(fn, *args, executor=...)` (or use a *custom* loop with `default_executor`).

## *Cancellation* is *the* *other* *half* *you* *must* *handle*

When a *task* is *cancelled* (a *timeout*, a *group* *error*), *your* *coroutine* *receives* *a* *`CancelledError`* *at* *the* *next* *`await`*. *The rule:*

- *If* you are *in* *a* *`try/except`*, **do not swallow `CancelledError`** unless you *re-raise* it. *Swallowing* it *means* "ignore the cancel," and the *cancel* *silently* *disappears*.
- *Wrap* *the* *unit* of *work* *in* a `try/finally` so *cleanup* (a *file* *handle*, a *temp* *buffer*) *runs* even *on* cancel.

For *the* *dup* *tool*, the *one* *line* *that* *matters*: *a* *per-file* *read* *that* is *cancelled* *must* *not* *leak* *a* *file* *handle*. *The* *`try/finally`* *around* *the* *`to_thread`* *read* *is* *that* *line*.

## *Where* *this* *shows* *up* *in* *the* *dup* *tool*

`internal/orchestrator/` is *one* coroutine that:

1. *Walks* the tree → *a list of paths* (I/O, *via* `to_thread`).
2. *Creates* a *bounded* *set* of *tasks* (`Semaphore` or *worker* pool) that *read + hash* each file.
3. *Awaits* the group, *collecting* `(hash, path)`; *one* bad file *is recorded, not fatal*.
4. *Hands* the collected pairs to `internal/report/` (grouping — *CPU*, *serial*, *trivial*).

*The* *concurrency* *is* *entirely* *in* *step* *2*. *Steps* *1* *and* *4* *are* *deliberately* *serial*: *walking* *and* *grouping* *do not* *benefit* *from* *fan-out*. *That* *restraint* *is* *the* *senior* *read*.

## *Run* *it*

`examples/ex2-gather-vs-wait.py`: *the same* *1000 sleeps*, *three ways* — *`gather`*, *`TaskGroup`*, *and* *manual `create_task` + `wait`*. *Compare* *the output shapes* (gather: ordered list; TaskGroup: structured; manual: you manage it). *The differences are the point.*
