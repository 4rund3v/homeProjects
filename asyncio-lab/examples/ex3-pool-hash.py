"""ex3: the A/B that proves docs/03 (process pool for CPU).

Hash a set of medium files three ways, TIMED:
  - on the loop (blocking)      -> worst
  - to_thread (GIL, serial)    -> ~serial
  - ProcessPoolExecutor (cores) -> ~cores x serial

Same data, same hash. The only variable is WHERE the hash runs.
Read docs/01 and docs/03 first.
"""

import asyncio
import hashlib
import os
import time
from concurrent.futures import ProcessPoolExecutor

N, SIZE = 32, 4 * 1024 * 1024
DATA = [os.urandom(SIZE) for _ in range(N)]


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


async def on_loop() -> float:
    t0 = time.time()
    for b in DATA:
        _sha(b)                    # blocks the loop
    return time.time() - t0


async def to_thread() -> float:
    loop = asyncio.get_running_loop()
    t0 = time.time()
    for b in DATA:
        await loop.run_in_executor(None, _sha, b)
    return time.time() - t0


async def to_pool(pool: ProcessPoolExecutor) -> float:
    loop = asyncio.get_running_loop()
    t0 = time.time()
    # fan out concurrently: submit all, await all
    await asyncio.gather(*(loop.run_in_executor(pool, _sha, b) for b in DATA))
    return time.time() - t0


async def main():
    a = await on_loop()
    b = await to_thread()
    pool = ProcessPoolExecutor(max_workers=os.cpu_count())
    c = await to_pool(pool)
    pool.shutdown(wait=False)
    print(f"cores={os.cpu_count()}  N={N} files x {SIZE//1024//1024}MiB")
    print(f"on-loop   {a:7.3f}s   (blocking; the anti-pattern — always the worst)")
    print(f"to_thread {b:7.3f}s   (GIL is RELEASED by hashlib; often near-optimal)")
    print(f"pool      {c:7.3f}s   (all cores; wins on LARGE files, can LOSE on small ones)")
    print(f"\nthread/pool = {b/c:.2f}   on-loop/pool = {a/c:.2f}")
    print("Read: hashlib releases the GIL, so to_thread is already fast for a hash. The pool only")
    print("wins when the CPU work dominates the pickling cost (large/many files). The on-loop")
    print("hash is ALWAYS the worst — it blocks the loop AND pays async overhead. That's the doc.")


if __name__ == "__main__":
    asyncio.run(main())
