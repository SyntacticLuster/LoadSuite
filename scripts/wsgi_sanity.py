"""Local WSGI sanity checks for Passenger deployments.

Use this on the *server* to isolate whether requests hang inside:
- the ASGI<->WSGI bridge (a2wsgi)
- FastAPI lifespan/startup
- or only when traversing LiteSpeed/Passenger proxying.

It imports `passenger_wsgi.application` (the real WSGI callable cPanel uses)
and either:
- probes a single request entirely in-process, or
- serves it via `wsgiref.simple_server` on localhost.

Examples (on server):
  python scripts/wsgi_sanity.py probe --script-name /FreightLens --path /api/health
  python scripts/wsgi_sanity.py serve --port 8081
  curl -v http://127.0.0.1:8081/FreightLens/api/health

If a probe hangs, it will dump Python stack traces after the timeout.
"""

from __future__ import annotations

import argparse
import faulthandler
import io
import os
import sys
import time
from typing import Any, Callable, Iterable, List, MutableMapping, Optional, Tuple


WSGIEnviron = MutableMapping[str, Any]
StartResponse = Callable[[str, List[Tuple[str, str]], Optional[Any]], Any]
WSGIApplication = Callable[[WSGIEnviron, StartResponse], Iterable[bytes]]


def _import_passenger_app() -> WSGIApplication:
    # Ensure repo root is on sys.path when running from scripts/.
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    import passenger_wsgi  # noqa: WPS433

    return passenger_wsgi.application  # type: ignore[return-value]


def _build_environ(
    *,
    method: str,
    script_name: str,
    path_info: str,
    query_string: str,
    host: str,
    scheme: str,
) -> WSGIEnviron:
    # Minimal valid WSGI environ.
    environ: WSGIEnviron = {
        "REQUEST_METHOD": method,
        "SCRIPT_NAME": script_name,
        "PATH_INFO": path_info,
        "QUERY_STRING": query_string,
        "SERVER_NAME": host,
        "SERVER_PORT": "443" if scheme == "https" else "80",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": scheme,
        "wsgi.input": io.BytesIO(b""),
        "wsgi.errors": sys.stderr,
        "wsgi.multithread": True,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
        "REMOTE_ADDR": "127.0.0.1",
        "CONTENT_LENGTH": "0",
        "CONTENT_TYPE": "",
    }
    return environ


def probe_once(
    *,
    method: str,
    script_name: str,
    path: str,
    query: str,
    timeout_s: float,
) -> int:
    app = _import_passenger_app()

    captured: dict[str, Any] = {"status": None, "headers": None}

    def start_response(status: str, headers: List[Tuple[str, str]], exc_info: Optional[Any] = None):
        captured["status"] = status
        captured["headers"] = headers
        return None

    faulthandler.enable()
    faulthandler.dump_traceback_later(timeout_s, repeat=False)

    t0 = time.time()
    result_iter = app(
        _build_environ(
            method=method,
            script_name=script_name,
            path_info=path,
            query_string=query,
            host="localhost",
            scheme="https",
        ),
        start_response,
    )

    body: bytes = b""
    try:
        for chunk in result_iter:
            if chunk:
                body += chunk
    finally:
        close = getattr(result_iter, "close", None)
        if callable(close):
            close()
        faulthandler.cancel_dump_traceback_later()

    dt_ms = (time.time() - t0) * 1000
    print(f"probe completed in {dt_ms:.1f}ms")
    print(f"status: {captured['status']}")
    print(f"headers: {captured['headers']}")
    print(f"body_bytes: {len(body)}")
    preview = body[:400]
    try:
        print("body_preview:")
        print(preview.decode("utf-8", errors="replace"))
    except Exception:
        print(repr(preview))

    if not captured["status"]:
        # start_response never called; treat as failure.
        return 2

    # Return nonzero on non-2xx.
    try:
        code = int(str(captured["status"]).split(" ", 1)[0])
    except Exception:
        return 3
    return 0 if 200 <= code < 300 else 4


def serve_local(*, host: str, port: int) -> int:
    # Serve the exact Passenger WSGI callable via wsgiref.
    from wsgiref.simple_server import WSGIRequestHandler, make_server

    app = _import_passenger_app()

    class QuietHandler(WSGIRequestHandler):
        def log_message(self, format: str, *args: Any):  # noqa: A003
            return

    httpd = make_server(host, port, app, handler_class=QuietHandler)
    sa = httpd.socket.getsockname()
    print(f"Serving Passenger WSGI app on http://{sa[0]}:{sa[1]}")
    print("Try: curl -v http://127.0.0.1:%d/FreightLens/api/health" % port)
    httpd.serve_forever()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_probe = sub.add_parser("probe", help="Call WSGI app in-process once")
    p_probe.add_argument("--method", default="GET")
    p_probe.add_argument("--script-name", default="/FreightLens")
    p_probe.add_argument("--path", default="/api/health")
    p_probe.add_argument("--query", default="")
    p_probe.add_argument("--timeout", type=float, default=15.0)

    p_serve = sub.add_parser("serve", help="Serve via wsgiref on localhost")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8081)

    args = parser.parse_args()

    if args.cmd == "probe":
        return probe_once(
            method=args.method,
            script_name=args.script_name,
            path=args.path,
            query=args.query,
            timeout_s=args.timeout,
        )

    if args.cmd == "serve":
        return serve_local(host=args.host, port=args.port)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
