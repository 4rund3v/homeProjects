"""Stage 5 (docs/04) + the delivery surface (docs/05).

The duplicate groups are reported, biggest first. The optional HTTP surface
is the k8s-Service story: a /healthz probe (is the pool ready?) and a /scan
endpoint that runs the whole pipeline on demand and returns JSON.
"""

import json
import os

from internal.io import Info, _walk


def report(dups: dict[str, list[str]], errors: list[Exception],
           total_files: int, total_bytes_scanned: int) -> str:
    lines: list[str] = []
    saved = _bytes_saved(dups)

    lines.append(f"Scanned {total_files} files ({total_bytes_scanned // (1024 * 1024)} MiB).")
    lines.append(f"Duplicate groups: {len(dups)}. Reclaimable: {saved // (1024 * 1024)} MiB "
                 f"(keep one copy per group).")

    for digest, paths in sorted(dups.items(), key=lambda kv: -len(kv[1])):
        size = _size_of_first(paths)
        lines.append(f"\n[{digest[:12]}…]  {len(paths)} copies, "
                     f"{(len(paths) - 1) * size} bytes waste")
        for p in sorted(paths):
            lines.append(f"   {p}")

    if errors:
        lines.append(f"\n{len(errors)} unreadable file(s) skipped, e.g.: {errors[0]!r}")

    return "\n".join(lines)


# --- helpers ----------------------------------------------------------------

def _bytes_saved(dups: dict[str, list[str]]) -> int:
    return sum((len(paths) - 1) * _size_of_first(paths) for paths in dups.values())


def _size_of_first(paths: list[str]) -> int:
    try:
        return os.stat(paths[0]).st_size
    except OSError:
        return 0


# --- the delivery surface (docs/05) -----------------------------------------

def serve_http(default_dirs: list[str], port: int, cap_value: int) -> int:
    """A tiny stdlib HTTP surface: GET /healthz, POST /scan.

    This is the thing that makes the tool a k8s Service: the readiness probe
    is /healthz (200 when the process pool can be built), and /scan triggers
    the full pipeline on demand. It re-uses the SAME pipeline the CLI does, so
    the concurrency logic is identical either way — only the surface differs.
    """
    import http.server
    import socketserver

    pool = _build_pool_once(cap_value)

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.path == "/healthz":
                self._send(200, json.dumps({"ok": True, "workers": pool._max_workers}))
            else:
                self._send(404, {})

        def do_POST(self):
            if self.path == "/scan":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    req = json.loads(body)
                except json.JSONDecodeError:
                    self._send(400, {"error": "bad json"})
                    return
                dirs = req.get("dirs") or default_dirs
                self._scan(dirs, cap_value, pool)
            else:
                self._send(404, {})

        def _scan(self, dirs, cap_value, pool):
            import asyncio
            from internal.orchestrator import by_size_candidates, group_by_hash
            from internal.hasher import hash_candidate

            async def _run():
                cap = asyncio.Semaphore(cap_value)
                infos = await asyncio.to_thread(_walk, dirs)
                candidates = by_size_candidates(infos)
                results = await asyncio.gather(
                    *(hash_candidate(c, cap, pool) for c in candidates),
                    return_exceptions=True)
                return group_by_hash(results)

            dups, errors = asyncio.run(_run())
            self._send(200, {"groups": dups, "skipped": len(errors)})

        def _send(self, code, obj):
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    with socketserver.ThreadingTCPServer(("0.0.0.0", port), Handler) as httpd:
        print(f"dupfind serving on :{port}  (GET /healthz, POST /scan)")
        httpd.serve_forever()
    return 0


def _build_pool_once(cap_value: int):
    from concurrent.futures import ProcessPoolExecutor
    return ProcessPoolExecutor(max_workers=cap_value or max(1, os.cpu_count()))
