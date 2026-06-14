"""
Centralized Error Handling Framework

Provides consistent error handling, logging, and recovery across all services.
"""

import logging
from enum import Enum
from functools import wraps
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ServiceError(Exception):
    """Base exception for all service errors"""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity,
        context: Optional[Dict] = None,
        original_error: Optional[Exception] = None,
    ):
        self.message = message
        self.severity = severity
        self.context = context or {}
        self.original_error = original_error
        super().__init__(message)

    def to_dict(self) -> Dict:
        """Convert error to dictionary for logging/API responses"""
        return {
            "error": self.message,
            "severity": self.severity.value,
            "context": self.context,
            "type": self.__class__.__name__,
        }


class LLMServiceError(ServiceError):
    """LLM-specific errors (timeout, rate limit, invalid response)"""

    pass


class ArchiMateValidationError(ServiceError):
    """ArchiMate validation errors"""

    pass


class DocumentProcessingError(ServiceError):
    """Document processing/parsing errors"""

    pass


class CachingError(ServiceError):
    """Caching service errors"""

    pass


class DatabaseError(ServiceError):
    """Database operation errors"""

    pass


def handle_service_errors(
    severity: ErrorSeverity = ErrorSeverity.MEDIUM, log_args: bool = False, reraise: bool = True
):
    """
    Decorator for consistent error handling across services

    Args:
        severity: Default severity if non-ServiceError exception occurs
        log_args: Whether to log function arguments (may contain sensitive data)
        reraise: Whether to re-raise exceptions after logging

    Usage:
        @handle_service_errors(severity=ErrorSeverity.HIGH, log_args=True)
        def process_document(document_path):
            ...
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            module_name = func.__module__

            try:
                logger.debug(f"Entering {module_name}.{func_name}")
                result = func(*args, **kwargs)
                logger.debug(f"Exiting {module_name}.{func_name}")
                return result

            except ServiceError as e:
                # Known service error - log with context
                log_method = getattr(logger, e.severity.value, logger.error)
                log_method(
                    f"Service error in {module_name}.{func_name}: {e.message}",
                    extra={
                        "severity": e.severity.value,
                        "context": e.context,
                        "function": func_name,
                        "module_name": module_name,
                        "error_type": type(e).__name__,
                    },
                    exc_info=e.original_error,
                )

                if reraise:
                    raise

                return None

            except Exception as e:
                # Unexpected error - log and wrap
                # Note: 'module' is a reserved field in LogRecord, use 'module_name' instead
                logger.exception(
                    f"Unexpected error in {module_name}.{func_name}: {str(e)}",
                    extra={
                        "function": func_name,
                        "module_name": module_name,
                        "error_type": type(e).__name__,
                    },
                )

                wrapped_error = ServiceError(
                    f"Unexpected error in {func_name}: {str(e)}",
                    severity=severity,
                    context={"function": func_name, "module": module_name},
                    original_error=e,
                )

                if reraise:
                    raise wrapped_error from e

                return None

        return wrapper

    return decorator


def log_performance(threshold_ms: float = 1000):
    """
    Decorator to log slow function executions

    Args:
        threshold_ms: Log warning if execution exceeds this threshold

    Usage:
        @log_performance(threshold_ms=500)
        def expensive_operation():
            ...
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time

            start_time = time.time()

            result = func(*args, **kwargs)

            elapsed_ms = (time.time() - start_time) * 1000

            if elapsed_ms > threshold_ms:
                logger.warning(
                    f"Slow execution: {func.__name__} took {elapsed_ms:.0f}ms (threshold: {threshold_ms}ms)",
                    extra={
                        "function": func.__name__,
                        "elapsed_ms": elapsed_ms,
                        "threshold_ms": threshold_ms,
                    },
                )
            else:
                logger.debug(f"{func.__name__} completed in {elapsed_ms:.0f}ms")

            return result

        return wrapper

    return decorator


def retry_on_transient_error(max_retries: int = 3, backoff_factor: float = 2.0):
    """
    DEPRECATED: Use app.services.core.retry_handler.retry_on_transient_error instead.

    This function is kept for backward compatibility but will be removed in a future version.
    The retry_handler version uses tenacity and provides better error handling.

    Decorator to retry operations on transient errors

    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Exponential backoff multiplier

    Usage:
        @retry_on_transient_error(max_retries=3, backoff_factor=2.0)
        def call_external_api():
            ...
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time

            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except (ConnectionError, TimeoutError) as e:
                    last_exception = e

                    if attempt < max_retries:
                        wait_time = backoff_factor**attempt
                        logger.warning(
                            f"Transient error in {func.__name__}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt + 1,
                                "max_retries": max_retries,
                                "wait_time": wait_time,
                                "error": str(e),
                            },
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"Max retries exceeded for {func.__name__}",
                            extra={"function": func.__name__, "max_retries": max_retries},
                        )

            # All retries exhausted
            raise LLMServiceError(
                f"Operation failed after {max_retries} retries",
                severity=ErrorSeverity.HIGH,
                context={"max_retries": max_retries},
                original_error=last_exception,
            )

        return wrapper

    return decorator
