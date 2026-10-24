"""The I/O-bound half: walk a tree and read file metadata.

Reading a directory is I/O, but NOT the kind of I/O that epoll multiplexes
(regular-file reads). So we do it in a thread via asyncio.to_thread.
docs/01 explains why; docs/02 explains to_thread.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Info:
    path: str
    size: int


def _walk(paths: list[str]) -> list[Info]:
    """Blocking. Runs in a thread. Returns one Info per regular file.

    A stat error (permission, a broken symlink, a file that vanished) is
    recorded by SKIPPING, never crashing the scan. docs/02 "one bad file
    must not cancel the scan."
    """
    out: list[Info] = []
    for root in paths:
        for dirpath, _dirs, filenames in os.walk(root):
            for name in filenames:
                p = os.path.join(dirpath, name)
                try:
                    st = os.stat(p)
                    out.append(Info(p, st.st_size))
                except OSError:
                    continue
    return out
