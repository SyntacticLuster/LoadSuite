from __future__ import annotations

import logging

try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
except ImportError:  # pragma: no cover - prod safety net when deps missing
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.warning("prometheus_client missing; metrics endpoint will be stubbed")

    class _Noop:
        def labels(self, *args, **kwargs):
            return self

        def inc(self, *_, **__):
            return None

        def observe(self, *_, **__):
            return None

    Counter = Histogram = lambda *_, **__: _Noop()  # type: ignore
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

    def generate_latest():  # type: ignore
        return b"# metrics disabled: prometheus_client missing\n"

# HTTP request metrics (low-cardinality labels)
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "route_template", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route_template"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)


def get_metrics_text() -> tuple[bytes, str]:
    """Return Prometheus metrics payload and content type."""

    return generate_latest(), CONTENT_TYPE_LATEST