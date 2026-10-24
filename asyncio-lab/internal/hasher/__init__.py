"""The CPU-bound half: SHA-256 a file, off the event loop.

The hash runs in a ProcessPoolExecutor worker process (docs/03):
  - it uses ALL cores (no GIL),
  - it streams in chunks (bounded memory for huge files),
  - only the path crosses the process boundary (the bytes never pickle).

`hash_candidate` is the async wrapper: it awaits run_in_executor so the loop
stays free while a worker computes. docs/01: CPU work must leave the loop.
"""

import asyncio
import hashlib
import os
from concurrent.futures import ProcessPoolExecutor

from internal.io import Info

CHUNK = 1 << 20  # 1 MiB


def _hash_path(path: str) -> str:
    """Runs in a WORKER PROCESS. Reads + hashes, streaming. Bounded memory."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def make_pool() -> ProcessPoolExecutor:
    return ProcessPoolExecutor(max_workers=os.cpu_count())


async def hash_candidate(info: Info, cap: asyncio.Semaphore, pool: ProcessPoolExecutor) -> tuple[str, str] | None:
    """One candidate: acquire backpressure, hash off-loop, return (digest, path).

    The Semaphore is the backpressure from docs/02 — it bounds how many hashes
    are in flight at once, so we don't queue more work than the pool can take.
    """
    async with cap:
        loop = asyncio.get_running_loop()
        digest = await loop.run_in_executor(pool, _hash_path, info.path)
        return (digest, info.path)
