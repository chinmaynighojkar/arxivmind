"""Request logging and rate limiting middleware."""

import time
import uuid

import structlog
from fastapi import FastAPI, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = structlog.get_logger()


def _client_ip(request: Request) -> str:
    """Return the real client IP, trusting a single upstream proxy layer."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_client_ip)

# In-memory counters — reset on every process restart, not persisted across deploys.
_request_count = 0
_error_count = 0
_total_latency_ms = 0


def setup_middleware(app: FastAPI) -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ]
    )

    @app.middleware("http")
    async def logging_middleware(request: Request, call_next) -> Response:
        global _request_count, _error_count, _total_latency_ms

        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        start = time.monotonic()

        response = await call_next(request)

        latency_ms = int((time.monotonic() - start) * 1000)
        _request_count += 1
        _total_latency_ms += latency_ms
        if response.status_code >= 400:
            _error_count += 1

        logger.info(
            "request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=latency_ms,
        )

        response.headers["X-Request-ID"] = request_id
        return response


def get_metrics() -> dict:
    avg_latency = _total_latency_ms // max(_request_count, 1)
    return {
        "request_count": _request_count,
        "error_count": _error_count,
        "avg_latency_ms": avg_latency,
    }
