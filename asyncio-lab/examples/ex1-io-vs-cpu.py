"""ex1: I/O-bound vs CPU-bound, MEASURED.  (Read docs/01 first.)

Three ways to hash N medium buffers:
  1. on the loop, in a tight await-free loop  -> BLOCKS the loop (WRONG, slowest)
  2. via to_thread                             -> 1 thread at a time (GIL, ~serial)
  3. via ProcessPoolExecutor (N cores)         -> ~N x serial  (the correct CPU answer)

The point: method 1 is WORSE than method 2. It blocks AND pays async overhead.
Never make CPU work run on the loop.
"""

import asyncio
import hashlib
import os
import time
from concurrent.futures import ProcessPoolExecutor

N = 64                    # number of "files"
SIZE = 8 * 1024 * 1024    # 8 MiB each -> a real hash, not a no-op
DATA = [os.urandom(SIZE) for _ in range(N)]


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# --- 1) ON THE LOOP: a plain sync hash loop that never yields --------------
async def hash_on_loop():
    out = []
    for b in DATA:
        out.append(_sha(b))          # no await -> blocks the loop for the whole hash
    return out


# --- 2) to_thread: one thread at a time (GIL bounds it) ----------------------
async def hash_to_thread():
    loop = asyncio.get_running_loop()
    out = []
    for b in DATA:
        out.append(await loop.run_in_executor(None, _sha, b))   # None = default thread pool
    return out


# --- 3) ProcessPool: all cores, no GIL --------------------------------------
async def hash_to_pool(pool: ProcessPoolExecutor):
    loop = asyncio.get_running_loop()
    out = []
    for b in DATA:
        out.append(await loop.run_in_executor(pool, _sha, b))
    return out


async def main():
    # on-loop
    t0 = time.time(); await hash_on_loop(); on_loop = time.time() - t0

    # to_thread
    t0 = time.time(); await hash_to_thread(); thr = time.time() - t0

    # process-pool
    pool = ProcessPoolExecutor(max_workers=os.cpu_count())
    t0 = time.time(); await hash_to_pool(pool); ppool = time.time() - t0
    pool.shutdown(wait=False)

    print(f"cores: {os.cpu_count()}   N={N} files x {SIZE//1024//1024}MiB")
    print(f"on-loop   : {on_loop:7.3f}s   <- worst: blocks the loop AND async overhead")
    print(f"to_thread : {thr:7.3f}s   <- GIL is RELEASED by hashlib; near-optimal here")
    print(f"pool      : {ppool:7.3f}s   <- pickles the bytes across the boundary")
    print(f"\nthread/pool = {thr/ppool:.2f}. For a HASH hashlib releases the GIL, so a THREAD is already fast,")
    print("and the pool only pays the cost of PICKLING each buffer. So for medium files the pool is")
    print("NOT faster — it's the same work plus serialization. The pool genuinely wins only for HUGE")
    print("files, where you hash the PATH in the worker (read there) and never pickle the bytes.")
    print("The on-loop hash is ALWAYS the worst — it blocks the loop. That's the invariant lesson.")


if __name__ == "__main__":
    asyncio.run(main())
