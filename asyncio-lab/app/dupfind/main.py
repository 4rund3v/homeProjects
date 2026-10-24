"""dupfind CLI: the assembly of the five stages (docs/04).

Run:  uv run dupfind /some/dir [/other/dir]

The concurrency lives ENTIRELY in stage 3 (the hash fan-out). Stages 1,2,4,5
are serial — that restraint is the senior read. The correctness invariant:
the duplicate groups are identical whether the pool has 1 worker or N.
"""

import argparse
import asyncio
import sys

from internal.io import Info, _walk
from internal.hasher import make_pool, hash_candidate
from internal.orchestrator import by_size_candidates, group_by_hash
from internal.report import report


async def run(paths: list[str], cap_value: int) -> int:
    cap = asyncio.Semaphore(cap_value)

    # Stage 1: walk (I/O, in a thread)
    infos: list[Info] = await asyncio.to_thread(_walk, paths)

    # Stage 2: group by size (serial, the free optimization)
    candidates = by_size_candidates(infos)

    # Stage 3: hash the candidates (CPU, in a process pool, bounded)
    pool = make_pool()
    try:
        results = await asyncio.gather(
            *(hash_candidate(c, cap, pool) for c in candidates),
            return_exceptions=True,
        )
    finally:
        pool.shutdown(wait=False)

    # Stage 4: group by hash (serial)
    dups, errors = group_by_hash(results)

    # Stage 5: report
    total_bytes = sum(i.size for i in infos)
    print(report(dups, errors, len(infos), total_bytes))
    return 0


def cli() -> int:
    ap = argparse.ArgumentParser(description="Find duplicate files by SHA-256 hash.")
    ap.add_argument("dirs", nargs="+", help="Directories to scan")
    ap.add_argument("--concurrency", type=int, default=None,
                    help="Max in-flight hashes (default: cpu count)")
    ap.add_argument("--serve", action="store_true",
                    help="Serve an HTTP surface (see docs/05) instead of scanning")
    ap.add_argument("--port", type=int, default=8080, help="Port for --serve")
    args = ap.parse_args()

    if args.serve:
        from internal.report import serve_http   # delivery layer (docs/05)
        cap_value = args.concurrency or _default_cap()
        return serve_http(args.dirs, args.port, cap_value)

    cap_value = args.concurrency or _default_cap()
    return asyncio.run(run(args.dirs, cap_value))


def _default_cap() -> int:
    import os
    return os.cpu_count() or 1


if __name__ == "__main__":
    sys.exit(cli())
