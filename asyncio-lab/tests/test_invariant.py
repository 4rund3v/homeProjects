"""The correctness test: concurrency must not change the output.

CLAUDE.md invariant: the duplicate groups are IDENTICAL whether the pool has
1 worker or N. This test makes that concrete: build a tree with known
duplicates, run the pipeline at cap=1 and cap=8, and assert the group sets
match (as frozensets, so order is irrelevant).

Run:  uv run python -m pytest tests -q      (or: uv run python tests/test_invariant.py)
"""

import os
import tempfile
from pathlib import Path

# Make the project root importable whether we run via `python -m` or directly.
ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT))

from app.dupfind.main import run
from internal.orchestrator import by_size_candidates, group_by_hash
from internal.io import _walk
from internal.hasher import make_pool, hash_candidate
import asyncio


def _make_tree(root: str):
    """Write a small tree with known duplicates and one unique file."""
    os.makedirs(f"{root}/a", exist_ok=True)
    os.makedirs(f"{root}/b", exist_ok=True)
    with open(f"{root}/a/x.bin", "wb") as f:
        f.write(b"same-content")
    with open(f"{root}/b/y.bin", "wb") as f:
        f.write(b"same-content")      # duplicate of a/x.bin
    with open(f"{root}/b/z.bin", "wb") as f:
        f.write(b"unique")           # no duplicate
    with open(f"{root}/b/w.bin", "wb") as f:
        f.write(b"same-content")     # third copy


async def _groups(root: str, cap: int) -> set:
    cap_sem = asyncio.Semaphore(cap)
    infos = await asyncio.to_thread(_walk, [root])
    candidates = by_size_candidates(infos)
    pool = make_pool()
    try:
        results = await asyncio.gather(
            *(hash_candidate(c, cap_sem, pool) for c in candidates),
            return_exceptions=True)
    finally:
        pool.shutdown(wait=False)
    dups, _ = group_by_hash(results)
    return {frozenset(paths) for paths in dups.values()}


def test_concurrency_does_not_change_output():
    with tempfile.TemporaryDirectory() as root:
        _make_tree(root)
        g1 = asyncio.run(_groups(root, cap=1))
        g8 = asyncio.run(_groups(root, cap=8))
        # a/x.bin, b/y.bin, b/w.bin share content -> ONE group of 3 paths.
        expected = {frozenset([f"{root}/a/x.bin", f"{root}/b/y.bin", f"{root}/b/w.bin"])}
        assert g1 == expected, f"cap=1 gave {g1}"
        assert g8 == expected, f"cap=8 gave {g8}"
        assert g1 == g8, "concurrency level changed the output (INVARIANT BROKEN)"


if __name__ == "__main__":
    test_concurrency_does_not_change_output()
    print("PASS: duplicate groups identical at cap=1 and cap=8.")
