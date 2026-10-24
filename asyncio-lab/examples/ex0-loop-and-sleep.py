"""ex0: the event loop, felt.

Five coroutines that `await asyncio.sleep(1)` overlap -> ~1s total.
Five functions that `time.sleep(1)` serialize -> ~5s total.
The gap IS the I/O-concurrency win. Read docs/00 first.
"""

import asyncio
import time


async def a_slow():
    for _ in range(5):
        await asyncio.sleep(1)
    return "a done"


def sync_slow():
    for _ in range(5):
        time.sleep(1)  # BLOCKS the whole thread
    return "sync done"


async def main():
    # --- the async way: 5 coroutines overlap, 5s of sleeps -> ~1s wall ---
    t0 = time.time()
    results = await asyncio.gather(*(a_slow() for _ in range(5)))
    async_dt = time.time() - t0
    print(f"async (overlap):  {len(results)} results in {async_dt:.2f}s  (each has 5s of sleeps)")

    # --- the sync way: 5 calls serialize, 5s each -> ~25s wall ---
    # (We do NOT actually run the full 25s here; we show the arithmetic.)
    sync_earmark = 5 * 5
    print(f"sync  (serial):   would be {sync_earmark}s for the same 5 calls")
    print(f"gap:             {sync_earmark - async_dt:.2f}s — that gap is the concurrency win")


if __name__ == "__main__":
    asyncio.run(main())
