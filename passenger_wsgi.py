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


def _build_wsgi_application():
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
    return ASGIMiddleware(asgi_app)


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
        # This is the fastest way to learn where we're stuck on shared hosting.
        tb_file = None
        try:
            tb_path = _append_log_path("passenger_traceback.log")
            tb_file = open(tb_path, "a", encoding="utf-8")
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            tb_file.write(f"\n[{ts}] dump_traceback_later scheduled path={path_info!r} method={request_method!r}\n")
            tb_file.flush()
            faulthandler.dump_traceback_later(15.0, repeat=False, file=tb_file)
        except Exception as e:
            _debug_log("Failed to schedule faulthandler dump: " + repr(e))

        def _sr(status, headers, exc_info=None):
            _debug_log(f"REQ status={status} path={path_info!r}")
            try:
                faulthandler.cancel_dump_traceback_later()
            except Exception:
                pass
            try:
                if tb_file is not None:
                    tb_file.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] start_response status={status} path={path_info!r}\n")
                    tb_file.flush()
                    tb_file.close()
            except Exception:
                pass
            return start_response(status, headers, exc_info)

        try:
            result: Iterable[bytes] = wsgi_app(environ, _sr)
            return result
        except Exception:
            _debug_log("REQ exception: " + traceback.format_exc().strip())
            raise
        finally:
            try:
                faulthandler.cancel_dump_traceback_later()
            except Exception:
                pass
            try:
                if tb_file is not None and not tb_file.closed:
                    tb_file.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] request finished path={path_info!r}\n")
                    tb_file.flush()
                    tb_file.close()
            except Exception:
                pass

    return _app


# Passenger expects an 'application' callable
application = _with_request_debug(_build_wsgi_application())
_debug_log("WSGI application ready")
