"""
Structured request/response logging with correlation IDs.

Provides a ``StructuredLogger`` that emits JSON-structured log entries with
request context (method, path, user, duration, status).  Designed for new
modular endpoints; legacy modules are unaffected.

Usage::

    from app.core.observability.logging import request_logger

    @app.after_request
    def log_response(response):
        request_logger.log_request(response)
        return response
"""

import logging
import time
import uuid
from typing import Optional

from flask import g, request

logger = logging.getLogger("app.core.observability")


class StructuredLogger:
    """Structured request logger with correlation ID support."""

    def __init__(self, logger_name: str = "app.core.observability"):
        self._logger = logging.getLogger(logger_name)

    def attach_request_id(self) -> str:
        """Generate and attach a request ID to ``g`` and ``request``.

        Call this in ``before_request``.  Returns the generated ID.
        """
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:12]
        g.request_id = req_id
        g.request_start = time.monotonic()
        request.request_id = req_id  # type: ignore[attr-defined]
        return req_id

    def get_request_id(self) -> str:
        """Return current request ID (or 'unknown')."""
        return getattr(g, "request_id", "unknown")

    def log_request(self, response, *, include_user: bool = True) -> None:
        """Log a completed request with structured context.

        Call this in ``after_request``.
        """
        duration_ms = 0.0
        if hasattr(g, "request_start"):
            duration_ms = round((time.monotonic() - g.request_start) * 1000, 2)

        user_id = None
        if include_user:
            try:
                from flask_login import current_user

                if current_user.is_authenticated:
                    user_id = getattr(current_user, "id", None)
            except Exception:
                pass

        extra = {
            "request_id": self.get_request_id(),
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
            "ip": request.remote_addr,
        }

        if response.status_code >= 500:
            self._logger.error("Request failed: %s %s -> %s", request.method, request.path, response.status_code, extra=extra)
        elif response.status_code >= 400:
            self._logger.warning("Client error: %s %s -> %s", request.method, request.path, response.status_code, extra=extra)
        else:
            self._logger.info("Request: %s %s -> %s (%.1fms)", request.method, request.path, response.status_code, duration_ms, extra=extra)

    def log_service_call(
        self,
        service_name: str,
        method: str,
        duration_ms: float,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Log an internal service call for tracing."""
        extra = {
            "request_id": self.get_request_id(),
            "service": service_name,
            "method": method,
            "duration_ms": round(duration_ms, 2),
            "success": success,
        }
        if error:
            extra["error"] = error

        if success:
            self._logger.debug("Service call: %s.%s (%.1fms)", service_name, method, duration_ms, extra=extra)
        else:
            self._logger.warning("Service call failed: %s.%s — %s", service_name, method, error, extra=extra)


request_logger = StructuredLogger()
