"""Passenger WSGI entry point for cPanel Python hosting.

This file is required by Phusion Passenger (used by cPanel) to load the application.
"""

import sys
import os

# Add application directory to Python path
app_dir = os.path.dirname(__file__)
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(app_dir, '.env'))
except ImportError:
    pass  # dotenv not installed, rely on system environment variables

# Import the FastAPI application
from app.main import app as asgi_app


def _build_wsgi_application():
    """Build a WSGI callable for Passenger.

    cPanel's "Setup Python App" uses Phusion Passenger in WSGI mode.
    FastAPI is ASGI, so we adapt it.
    """

    try:
        from a2wsgi import ASGIMiddleware
    except Exception as e:  # pragma: no cover
        # Passenger will surface this as a 500; the details should land in the app error log.
        raise RuntimeError(
            "Missing dependency 'a2wsgi'. Install it in the app virtualenv (e.g. pip install a2wsgi)."
        ) from e

    return ASGIMiddleware(asgi_app)


# Passenger expects an 'application' callable
application = _build_wsgi_application()
