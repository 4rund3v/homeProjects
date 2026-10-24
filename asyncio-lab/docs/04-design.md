# 04 — Design: the dup-find tool, assembled from the four `internal/` modules

This doc is the *blueprint*. The *code* in `cmd/` and `internal/` is a *direct* transcription of it. Read *this* first; the code is the *mechanical* version.

## The *input* and the *output*

**In:** a *directory* (or a *list of directories*).
**Out:** *groups of duplicates*. Each group = *one* *distinct hash* + *the full paths* that share it. *Plus* *a* *count* of *total* files / *unique* hashes / *duplicated* bytes *saved*.

*The* *invariant* (CLAUDE.md): *the grouping is* **correct regardless of concurrency**. *Running with* *1* *worker* *or* *64* *produces* *the* *identical* *set of* *duplicate groups*. *Concurrency changes* *speed*, *never output*.

## The *five* *stages*, *and* *which* *run* *where*

```
Stage            What                          Runs on
─────────────────────────────────────────────────────────────────
1. walk           scandir, build the file list   to_thread (I/O)
2. group-by-size  bucket files by size (fast dedupe)  serial (CPU, trivial)
3. hash           sha256 the remaining files     ProcessPool (CPU, all cores)
4. group-by-hash  dict[hash] -> [paths]          serial (CPU, trivial)
5. report         print duplicate groups         serial (I/O: the print)
```

*The* *stage 2* is *the* *senior* *optimization* *no one* *expects* *from* *an* *async* *tool*: *before* *you hash anything, group* *by* *file size*. *Two* *files* *of* *different sizes* *are* *guaranteed* *not* *to* *match*, *so* *you skip* *their* *hash* *entirely*. *For* *a* *dir* *with* *many* *unique* *files*, *this* *cuts* *the* *hash work by an order of magnitude*. *It costs* *nothing* *to* *compute* (the *size* is *in* *the* *`scandir`* *result*). *This* *is* *a* *real* *dup-finder* *trick*, *and* *it* *is* *the* *kind* *of thing* *that* *makes* *the* *tool* *actually fast*, *not* *just* *concurrent*.

## *Stage* *1* — walk, *in* *a thread*

*Walking* *a* *directory tree* *is* *I/O* *(`scandir`* *is* *a syscall)*, *but* *not* *the* *kind* *of* *I/O* *that* *`epoll`* *multiplexes*. *So* *it* *runs* *via* *`to_thread`*:

```python
def _walk(paths: list[str]) -> list[Info]:        # blocking, runs in a thread
    out = []
    for root in paths:
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                p = os.path.join(dirpath, name)
                try:
                    st = os.stat(p)                # one stat per file
                    out.append(Info(p, st.st_size))
                except OSError:
                    pass                            # skip unreadable; don't crash the scan
    return out

# in the loop:
infos = await asyncio.to_thread(_walk, paths)
```

*The* *`try/except`* *is* *the* *rule* *from* *`02`*: *one bad file* *never* *crashes* *the scan*. *Record it* *if* *you* *want* (a `--verbose` list), *but* *do not fail* *the whole run*.

## *Stage* *2* — group by size, *serial*

```python
by_size: dict[int, list[Info]] = defaultdict(list)
for info in infos:
    by_size[info.size].append(info)
# only sizes with >1 file can have duplicates
candidates = [infos for size, infos in by_size.items() if len(infos) > 1]
```

*This is* *serial, deliberately*. *A dict update* *is not a* *concurrency win*. *The restraint is the point* (`02`).

## *Stage* *3* — hash the candidates, *in a process pool*

```python
pool = ProcessPoolExecutor(max_workers=cpu_count())

def _hash_path(path: str) -> str:                  # runs in a WORKER PROCESS
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

async def hash_candidate(info: Info, cap: asyncio.Semaphore) -> tuple[str, str] | None:
    async with cap:                                  # backpressure: bounded in-flight
        loop = asyncio.get_running_loop()
        digest = await loop.run_in_executor(pool, _hash_path, info.path)
        return (digest, info.path)

results = await asyncio.gather(
    *(hash_candidate(c, cap) for c in candidates),
    return_exceptions=True,                          # one unreadable file is not fatal
)
```

*The* *`Semaphore`* *(`cap`)* *bounds* *the* *in-flight* *hashes* *to* *the pool size* (or *a little below*). *`return_exceptions=True`* *means* *a* *corrupt* *file* *records an error*, *doesn't cancel* *the scan* (`02`).

## *Stage* *4* — group by hash, *serial*

```python
by_hash: dict[str, list[str]] = defaultdict(list)
errors = []
for r in results:
    if isinstance(r, BaseException):
        errors.append(r)
        continue
    digest, path = r
    by_hash[digest].append(path)

dups = {h: ps for h, ps in by_hash.items() if len(ps) > 1}   # keep only real duplicates
```

*Again* *serial*. *The* *concurrency* *ended at stage 3*. *Stages* *4-5* *are* *data-munging*, *not* *a* *fan-out*.

## *Stage* *5* — report

```python
def report(dups, errors, total_files, total_bytes_saved):
    for digest, paths in sorted(dups.items(), key=lambda kv: -len(kv[1])):
        print(f"[{digest}]  {len(paths)} copies")
        for p in sorted(paths):
            print(f"   {p}")
    if errors:
        print(f"\n{len(errors)} unreadable file(s) skipped")
```

*Sort by group size first* (the *biggest* duplicate sets *are* the *most valuable* — *the* *most* *bytes* *you* *recover*). *That* *is* *the* *UX* *a* *senior* *engineer* *picks*, *not* *an* *arbitrary* *order*.

## The *single-file* *assembly* (`cmd/dupfind/main.py`)

```python
async def main():
    paths = argv_paths                      # from argv
    cap = asyncio.Semaphore(cpu_count())
    infos = await asyncio.to_thread(_walk, paths)
    candidates = _by_size_candidates(infos)
    pool = ProcessPoolExecutor()
    try:
        results = await asyncio.gather(
            *(hash_candidate(c, cap) for c in candidates),
            return_exceptions=True)
    finally:
        pool.shutdown(wait=False)
    dups, errors = _group_by_hash(results)
    report(dups, errors, len(infos), _bytes_saved(dups))

if __name__ == "__main__":
    asyncio.run(main())
```

*The* *`try/finally`* *around* *the pool* *is* *the* *cleanup* *from* *`02`*: *even if* *a cancel lands*, *the pool shuts down*. *The* *`hash_candidate` closure* *captures `cap` and `pool`* — *pass state in*, *don't* *use* *globals* (CLAUDE.md anti-goal).

## The *four* *modules*, *one* *responsibility* *each*

| Module | Responsibility | Doc |
|---|---|---|
| `internal/io/` | walk + `to_thread` reads | `02` |
| `internal/hasher/` | `_hash_path` + `hash_candidate` + the pool | `03` |
| `internal/orchestrator/` | the 5 stages, the `Semaphore`, the `gather` | `04` (this) |
| `internal/report/` | group-by-size, group-by-hash, print | `04` (this) |

*Each module is ~50 lines. The understanding is the* *`docs/`*; *the code is* *the* *transcription.*

## The *correctness* *check* (CLAUDE.md invariant, *made testable*)

*The test that* *proves* *the invariant: run the* *tool three ways — `max_workers=1`, `=4`, `=8` — on the* *same* *tree. The* *duplicate groups (as a set of frozensets of paths) must be* *identical*. Only the* *timing* *differs.* *That* *test is the* *definition of "done" for this* *project:* *concurrency* *is* *correct when it* *changes nothing but speed.*
