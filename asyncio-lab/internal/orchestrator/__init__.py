"""Stage 2-4 of the pipeline (docs/04): group-by-size, then group-by-hash.

These are deliberately SERIAL. A dict update is not a concurrency win — the
restraint is the point (docs/02). The only fan-out in the whole tool is the
hash stage; everything here is plain data-munging.
"""

from collections import defaultdict

from internal.io import Info


def by_size_candidates(infos: list[Info]) -> list[Info]:
    """Stage 2: the senior optimization.

    Two files of different sizes CANNOT be duplicates. So we only hash files
    that share a size with at least one other file. For a tree of mostly-unique
    files this cuts the hashing work by an order of magnitude, for free — the
    size is already in the Info from the walk.
    """
    by_size: dict[int, list[Info]] = defaultdict(list)
    for info in infos:
        by_size[info.size].append(info)
    return [i for size, group in by_size.items() if len(group) > 1 for i in group]


def group_by_hash(results: list) -> tuple[dict[str, list[str]], list[Exception]]:
    """Stage 4: collect (digest, path) pairs into groups; keep only real dups.

    `results` may contain exceptions (from gather return_exceptions=True);
    those become the returned error list, NOT a crash.
    """
    by_hash: dict[str, list[str]] = defaultdict(list)
    errors: list[Exception] = []
    for r in results:
        if isinstance(r, BaseException):
            errors.append(r)
            continue
        digest, path = r
        by_hash[digest].append(path)
    dups = {h: ps for h, ps in by_hash.items() if len(ps) > 1}
    return dups, errors
