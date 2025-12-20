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
from app.main import app

# Passenger expects an 'application' callable
application = app
