"""
Error handlers — canonical re-export.

Source: app/utils/error_handlers.py
"""

from app.utils.error_handlers import (
    format_error_response,
    register_error_handlers,
    safe_db_operation,
    safe_route,
)

__all__ = [
    "format_error_response",
    "register_error_handlers",
    "safe_route",
    "safe_db_operation",
]
