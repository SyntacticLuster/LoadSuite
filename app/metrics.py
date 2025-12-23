from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

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