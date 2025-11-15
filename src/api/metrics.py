"""
Phase 6: Prometheus metrics for API (request count, latency by endpoint and status).
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Request count by method, endpoint (path template), status class (2xx, 4xx, 5xx)
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_class"],
)

# Request duration in seconds
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)


def status_class(status_code: int) -> str:
    """Return 2xx, 4xx, 5xx for Prometheus labels."""
    if status_code < 300:
        return "2xx"
    if status_code < 500:
        return "4xx"
    return "5xx"


def normalize_path(path: str) -> str:
    """Normalize path to endpoint label (e.g. /books/{id} -> /books)."""
    if not path or path == "/":
        return path or "/"
    parts = path.strip("/").split("/")
    # Keep first segment as endpoint (e.g. books, search, query)
    return "/" + (parts[0] if parts else "")


def get_metrics_content_type() -> str:
    return CONTENT_TYPE_LATEST


def get_metrics_bytes() -> bytes:
    return generate_latest()
