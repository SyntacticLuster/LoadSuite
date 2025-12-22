"""Passenger WSGI entry point for cPanel Python hosting.

This file is required by Phusion Passenger (used by cPanel) to load the application.
"""

from __future__ import annotations

import os
import sys
import time
import traceback
import faulthandler
import json
import asyncio
import threading
from typing import Iterable

# Add application directory to Python path
app_dir = os.path.dirname(__file__)
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)


def _debug_log(message: str) -> None:
    """Best-effort debug log for shared hosting.

    cPanel/Passenger logs can be opaque; this gives us something we can inspect
    via File Manager even when stderr.log stays empty.
    """

    try:
        tmp_dir = os.path.join(app_dir, "tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        log_path = os.path.join(tmp_dir, "passenger_debug.log")
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
    except Exception:
        # Avoid breaking app load because logging failed.
        pass


def _append_log_path(filename: str) -> str:
    tmp_dir = os.path.join(app_dir, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    return os.path.join(tmp_dir, filename)


def _write_json_response(start_response, *, status: str, payload: dict) -> list[bytes]:
    body = (json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
    ]
    start_response(status, headers)
    return [body]

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(app_dir, '.env'))
except ImportError:
    pass  # dotenv not installed, rely on system environment variables

_debug_log("passenger_wsgi.py imported")

# Import the FastAPI application
try:
    from app.main import app as asgi_app
    _debug_log("Imported app.main:asgi_app")
except Exception:
    _debug_log("Failed to import app.main: " + traceback.format_exc().strip())
    raise


_wsgi_app = None
_wsgi_app_pid: int | None = None
_wsgi_app_lock = threading.Lock()


def _create_wsgi_application():
    """Build a WSGI callable for Passenger.

    cPanel's "Setup Python App" uses Phusion Passenger in WSGI mode.
    FastAPI is ASGI, so we adapt it.
    """

    try:
        from a2wsgi import ASGIMiddleware
    except Exception as e:  # pragma: no cover
        _debug_log("Missing dependency a2wsgi: " + repr(e))
        # Passenger will surface this as a 500; the details should land in the app error log.
        raise RuntimeError(
            "Missing dependency 'a2wsgi'. Install it in the app virtualenv (e.g. pip install a2wsgi)."
        ) from e

    _debug_log("Building ASGI->WSGI adapter")

    # Passenger may pre-fork worker processes. Threads created before a fork can
    # become inert/broken in the child. So we create an event loop thread per-PID
    # and recreate the adapter if PID changes.
    loop = asyncio.new_event_loop()

    def _run_loop() -> None:
        try:
            asyncio.set_event_loop(loop)
            loop.run_forever()
        except Exception:
            _debug_log("ASGI loop thread crashed: " + traceback.format_exc().strip())
            raise

    thread = threading.Thread(target=_run_loop, daemon=True)
    thread.start()
    _debug_log("ASGI loop thread started")

    return ASGIMiddleware(asgi_app, loop=loop)


def _get_wsgi_application():
    """Get (or rebuild) the WSGI app.

    If Passenger pre-forked after import, the loop thread in the child may not be
    alive. We detect PID changes and rebuild.
    """

    global _wsgi_app, _wsgi_app_pid
    pid = os.getpid()
    with _wsgi_app_lock:
        if _wsgi_app is None or _wsgi_app_pid != pid:
            _debug_log(f"(re)initializing WSGI adapter for pid={pid}")
            _wsgi_app = _create_wsgi_application()
            _wsgi_app_pid = pid
        return _wsgi_app


def _with_request_debug(wsgi_app):
    def _app(environ, start_response):
        path_info = environ.get("PATH_INFO", "")
        script_name = environ.get("SCRIPT_NAME", "")
        request_method = environ.get("REQUEST_METHOD", "")

        # Some shared-hosting WSGI stacks provide an input stream that will block
        # unless CONTENT_LENGTH is set. a2wsgi will read the request body to
        # bridge WSGI->ASGI; for methods that should have no body, force 0.
        content_length = (environ.get("CONTENT_LENGTH") or "").strip()
        if request_method in {"GET", "HEAD", "DELETE", "OPTIONS"} and not content_length:
            environ["CONTENT_LENGTH"] = "0"
            content_length = "0"

        content_type = (environ.get("CONTENT_TYPE") or "").strip()

        _debug_log(
            "REQ start "
            f"method={request_method} script={script_name!r} path={path_info!r} "
            f"content_length={content_length!r} content_type={content_type!r}"
        )

        # Pure WSGI probe endpoint. This bypasses a2wsgi/FastAPI entirely.
        # If this returns but /api/health hangs, the problem is almost certainly
        # inside the ASGI<->WSGI bridge or FastAPI lifespan.
        if path_info == "/api/wsgi-health":
            return _write_json_response(
                start_response,
                status="200 OK",
                payload={
                    "status": "ok",
                    "probe": "wsgi",
                    "script_name": script_name,
                    "path": path_info,
                    "method": request_method,
                },
            )

        # Optional bypass of the main health endpoint for diagnosis.
        # Enable by setting WSGI_HEALTH_BYPASS=1 in the environment.
        if path_info == "/api/health" and os.environ.get("WSGI_HEALTH_BYPASS") in {"1", "true", "TRUE", "yes", "YES"}:
            _debug_log("REQ bypassing /api/health via WSGI_HEALTH_BYPASS")
            return _write_json_response(
                start_response,
                status="200 OK",
                payload={
                    "status": "healthy",
                    "bypassed": True,
                    "probe": "wsgi",
                    "script_name": script_name,
                    "path": path_info,
                    "method": request_method,
                },
            )

        # If the request hangs before headers are returned, schedule a stack dump.
        # IMPORTANT: Passenger often consumes the returned iterable later; the hang may
        # occur during iteration (after this function returns). So we keep the watchdog
        # alive until the iterable is exhausted / closed.
        tb_file = None
        watchdog_armed = False
        returned_iterable = False
        try:
            tb_path = _append_log_path("passenger_traceback.log")
            tb_file = open(tb_path, "a", encoding="utf-8")
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            tb_file.write(
                f"\n[{ts}] watchdog arm path={path_info!r} method={request_method!r} script={script_name!r}\n"
            )
            tb_file.flush()
            faulthandler.dump_traceback_later(15.0, repeat=False, file=tb_file)
            watchdog_armed = True
        except Exception as e:
            _debug_log("Failed to arm faulthandler watchdog: " + repr(e))

        def _sr(status, headers, exc_info=None):
            _debug_log(f"REQ status={status} path={path_info!r}")
            try:
                if tb_file is not None:
                    tb_file.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] start_response status={status} path={path_info!r}\n")
                    tb_file.flush()
            except Exception:
                pass
            return start_response(status, headers, exc_info)

        try:
            # Resolve the actual adapter at request time (fork-safe).
            resolved_app = _get_wsgi_application() if wsgi_app is None else wsgi_app
            result: Iterable[bytes] = resolved_app(environ, _sr)
            _debug_log(f"REQ wsgi_app returned iterable path={path_info!r}")

            def _cleanup(note: str) -> None:
                nonlocal watchdog_armed, tb_file
                try:
                    if watchdog_armed:
                        faulthandler.cancel_dump_traceback_later()
                        watchdog_armed = False
                except Exception:
                    pass
                try:
                    if tb_file is not None and not tb_file.closed:
                        tb_file.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] watchdog disarm ({note}) path={path_info!r}\n")
                        tb_file.flush()
                        tb_file.close()
                except Exception:
                    pass

            # Wrap the iterable so the watchdog stays armed until Passenger actually
            # consumes the response.
            def _iter_wrapped():
                first = True
                try:
                    for chunk in result:
                        if first:
                            first = False
                            _debug_log(f"REQ first chunk path={path_info!r} bytes={(len(chunk) if chunk is not None else 'None')} ")
                        yield chunk
                finally:
                    # If the underlying iterable supports close(), call it.
                    try:
                        close_fn = getattr(result, "close", None)
                        if callable(close_fn):
                            close_fn()
                    except Exception:
                        pass
                    _cleanup("iterable finished")

            class _WrappedIterable:
                def __iter__(self):
                    return _iter_wrapped()

                def close(self):
                    try:
                        close_fn = getattr(result, "close", None)
                        if callable(close_fn):
                            close_fn()
                    finally:
                        _cleanup("close()")

            returned_iterable = True
            return _WrappedIterable()
        except Exception:
            _debug_log("REQ exception: " + traceback.format_exc().strip())
            raise
        finally:
            # Only clean up here if we are NOT returning a streaming iterable.
            # If we returned an iterable, cleanup happens when Passenger exhausts/closes it.
            if not returned_iterable:
                try:
                    if watchdog_armed:
                        faulthandler.cancel_dump_traceback_later()
                        watchdog_armed = False
                except Exception:
                    pass
                try:
                    if tb_file is not None and not tb_file.closed:
                        tb_file.write(
                            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] watchdog disarm (early-exit) path={path_info!r}\n"
                        )
                        tb_file.flush()
                        tb_file.close()
                except Exception:
                    pass

    return _app


# Passenger expects an 'application' callable
application = _with_request_debug(None)
_debug_log("WSGI application ready")
