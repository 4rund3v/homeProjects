# 00 — The event loop: what `async` and `await` actually are

## The mental model, corrected

"Async = do things in parallel" is the wrong starting point. It is **cooperative concurrency on *one* thread.** There is *one* thread. There is *one* event loop. *Many* coroutines *take turns* on that thread. They never run *simultaneously* — they run *one at a time*, and each one *yields* back to the loop at a specific, *marked* point.

## A coroutine is a *function that can pause*

```python
async def fetch():
    data = await some_io()   #  ← the PAUSE POINT
    return data
```

Calling `fetch()` does *not* run it. It returns a **coroutine object** — a *dormant* function with a *pause point* baked in. It runs only when you *schedule* it on the loop:

```python
task = asyncio.create_task(fetch())   # schedule it; the loop will run it
result = await task                   # the loop runs fetch() up to its first `await`, then yields
```

The **`await` keyword** is the *only* place a coroutine yields. At an `await`, control goes back to the *event loop*, which runs the *next* ready coroutine, and comes *back* to this one when the awaited thing is *done*.

## The loop, as a *while* loop

The event loop is ~this, with no other machinery:

```python
while True:
    for task in ready_tasks:      # tasks that have a value to continue
        task.step()              # run the coroutine up to its next `await` (or completion)
    # when no task is ready:
    #   block, waiting for an I/O event (a socket readable, a timer) to wake us
```

The **readiness** of a task is decided by the *I/O multiplexer* underneath (`epoll` on Linux). "Is socket 7 readable yet?" is the *question* the loop asks the kernel *at once*, instead of *one blocking call per socket*. **That** is where the win comes from: one thread, *one* multiplexer, *many* sockets.

## `async`/`await` are *syntactic*, not *magical*

- `async def` = "this function *pauses*; it returns a coroutine object, not a value."
- `await X` = "pause *here* until *X* is ready, then continue with *X*'s value."
- **Rule 1:** `await` is only legal *inside* an `async def`. You cannot `await` in a plain `def` (a plain `def` has no pause point — the loop has nothing to hand back to).
- **Rule 2:** a coroutine you *do not* `await` (or schedule) **never runs**. `fetch()` with no `await fetch()` does *nothing*. That is the #1 beginner bug: "why did my async function not run?" → you forgot to schedule it.

## The *single-thread* constraint, stated plainly

Because it is *one* thread: **any code that *blocks* the thread blocks *every* coroutine.** A blocking `time.sleep(5)` (not `await asyncio.sleep(5)`) *freezes* the whole loop for 5 s. A CPU hash loop *freezes* the whole loop while it runs. This is not a footnote — it is *the* reason the next doc exists.

## The two `sleep`s (the smallest possible proof)

```python
import time, asyncio

def sync():
    t0 = time.time()
    for _ in range(5): time.sleep(1)   # BLOCKS the thread
    return time.time() - t0

async def a():
    t0 = time.time()
    for _ in range(5): await asyncio.sleep(1)   # YIELDS to the loop
    return time.time() - t0
```

Run `await asyncio.gather(a(), a(), a())`: the *three* `a()`s *overlap* (each yields, the others run). Total ≈ **5 s**, not 15. Now do the same with the *sync* version: the three *serialize*. Total = **15 s**. The *5s vs 15s* gap is *exactly* the I/O-concurrency win. Run `examples/ex0` to *feel* it.

## What a *task* is vs a *coroutine*

- A **coroutine** (`fetch()`) = a *dormant* function, not yet running.
- A **task** (`asyncio.create_task(fetch())`) = a coroutine the *loop owns and schedules*. Tasks run *independently*; you `await` a task to collect its result.
- `asyncio.gather(*coros)` = a shortcut: wrap *many* coroutines in tasks and *await* them *together*, returning results *in input order*.

## Where this shows up in the dup tool

The tool's *orchestrator* (`internal/orchestrator/`) is *one* coroutine that:
1. *walks* the tree (I/O — `await` the `os.scandir` via `to_thread`),
2. *spawns* one task per file (or a *bounded* set),
3. *awaits* the group, *collecting* (hash, path) pairs.

The *walk* and the *reads* are the **I/O-bound** half (`01`). The *hash* is the **CPU-bound** half that must *not* run *on* this loop (`03`).

## Run it

`examples/ex0-loop-and-sleep.py` — five coroutines that `await asyncio.sleep`, and the same in `time.sleep`. Time both. *5s vs 25s* is the whole story of this doc.
