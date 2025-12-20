"""Structured logging utility for LoadSuite.

Provides a minimal, configurable logging scaffold that can be
expanded later without overhauling the existing application.

Features:
- Structured JSON logging support
- Context injection (request IDs, user IDs, etc.)
- Log level configuration
- Easy integration with existing code

Usage:
    from app.logging import get_logger
    
    logger = get_logger(__name__)
    logger.info("Load scored", load_id="LOAD-123", score=85.5)
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


# Context variables for request-scoped data
_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_user_id: ContextVar[Optional[str]] = ContextVar("user_id", default=None)


@dataclass
class LogContext:
    """Holds contextual data for structured logging."""
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


def set_request_context(
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> None:
    """Set request-scoped context for logging.
    
    Call this at the start of each request to inject context
    into all log messages during that request.
    
    Args:
        request_id: Unique identifier for the request
        user_id: ID of the authenticated user (if any)
    """
    if request_id is not None:
        _request_id.set(request_id)
    if user_id is not None:
        _user_id.set(user_id)


def clear_request_context() -> None:
    """Clear request-scoped context.
    
    Call this at the end of each request.
    """
    _request_id.set(None)
    _user_id.set(None)


def get_request_context() -> LogContext:
    """Get the current request context."""
    return LogContext(
        request_id=_request_id.get(),
        user_id=_user_id.get(),
    )


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging output."""
    
    def format(self, record: logging.LogRecord) -> str:
        # Build the log entry
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add location info
        if record.pathname:
            entry["location"] = {
                "file": record.filename,
                "line": record.lineno,
                "function": record.funcName,
            }
        
        # Add request context
        ctx = get_request_context()
        if ctx.request_id:
            entry["request_id"] = ctx.request_id
        if ctx.user_id:
            entry["user_id"] = ctx.user_id
        
        # Add extra fields from the log record
        if hasattr(record, "extra_fields"):
            entry["data"] = record.extra_fields
        
        # Add exception info if present
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(entry, default=str)


class ContextLogger(logging.LoggerAdapter):
    """Logger adapter that supports structured logging with extra fields.
    
    Example:
        logger.info("Load scored", load_id="LOAD-123", score=85.5)
    """
    
    def process(
        self,
        msg: str,
        kwargs: Dict[str, Any],
    ) -> tuple[str, Dict[str, Any]]:
        # Extract extra fields from kwargs
        extra_fields = {
            k: v for k, v in kwargs.items() 
            if k not in ("exc_info", "stack_info", "stacklevel", "extra")
        }
        
        # Clean kwargs for the base logger
        clean_kwargs = {
            k: v for k, v in kwargs.items()
            if k in ("exc_info", "stack_info", "stacklevel")
        }
        
        # Attach extra fields to be picked up by the formatter
        extra = kwargs.get("extra", {})
        extra["extra_fields"] = extra_fields
        clean_kwargs["extra"] = extra
        
        return msg, clean_kwargs


# Module-level configuration
_configured = False
_use_structured = False


def configure_logging(
    level: str = "INFO",
    structured: bool = False,
    stream: Any = None,
) -> None:
    """Configure the logging system.
    
    Call this once at application startup.
    
    Args:
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        structured: If True, output JSON-formatted logs
        stream: Output stream (defaults to sys.stderr)
    """
    global _configured, _use_structured
    
    if _configured:
        return  # Only configure once
    
    _use_structured = structured
    root_logger = logging.getLogger("loadsuite")
    root_logger.setLevel(getattr(logging, level.upper()))
    
    handler = logging.StreamHandler(stream or sys.stderr)
    
    if structured:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
    
    root_logger.addHandler(handler)
    _configured = True


def get_logger(name: str) -> ContextLogger:
    """Get a logger instance for the given name.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        ContextLogger that supports structured logging
    
    Example:
        logger = get_logger(__name__)
        logger.info("Operation completed", duration_ms=45, records=100)
    """
    # Ensure we're under the loadsuite namespace
    if not name.startswith("loadsuite"):
        name = f"loadsuite.{name}"
    
    base_logger = logging.getLogger(name)
    return ContextLogger(base_logger, {})


# Convenience function for quick setup
def setup_dev_logging() -> None:
    """Quick setup for development with human-readable output."""
    configure_logging(level="DEBUG", structured=False)


def setup_prod_logging() -> None:
    """Quick setup for production with structured JSON output."""
    configure_logging(level="INFO", structured=True)
