"""Passenger WSGI entry point for cPanel Python hosting.

This file is required by Phusion Passenger (used by cPanel) to load the application.
"""

from __future__ import annotations

import os
import sys
import time
import traceback

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

        def _sr(status, headers, exc_info=None):
            _debug_log(f"REQ status={status} path={path_info!r}")
            return start_response(status, headers, exc_info)

        try:
            return wsgi_app(environ, _sr)
        except Exception:
            _debug_log("REQ exception: " + traceback.format_exc().strip())
            raise

    return _app


# Passenger expects an 'application' callable
application = _with_request_debug(_build_wsgi_application())
_debug_log("WSGI application ready")
