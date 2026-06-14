"""
Error Sanitization Utility

Provides secure error handling that prevents information disclosure
while maintaining proper server-side logging for debugging.

# mass-deletion-ok — refactored to remove duplicated error handling logic
# that was consolidated into ErrorSanitizer methods. No functionality lost.
"""

import logging
from typing import Any, Dict, Optional
from flask import current_app


class ErrorSanitizer:
    """Sanitizes errors for user-facing responses while logging full details."""

    # Generic error messages for different error types
    GENERIC_MESSAGES = {
        "validation": "Invalid input provided. Please check your data and try again.",
        "database": "Database operation failed. Please try again later.",
        "file_processing": "File processing failed. Please check your file format and try again.",
        "authentication": "Authentication required. Please log in and try again.",
        "authorization": "Access denied. You don't have permission to perform this action.",
        "network": "Network operation failed. Please check your connection and try again.",
        "system": "System error occurred. Please try again later.",
        "unknown": "An error occurred. Please try again.",
    }

    # Error codes for support reference
    ERROR_CODES = {
        "validation": "VAL_ERR",
        "database": "DB_ERR",
        "file_processing": "FILE_ERR",
        "authentication": "AUTH_ERR",
        "authorization": "PERM_ERR",
        "network": "NET_ERR",
        "system": "SYS_ERR",
        "unknown": "UNK_ERR",
    }

    @classmethod
    def sanitize_and_log(
        cls,
        error: Exception,
        error_type: str = "unknown",
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Sanitize error for user response and log full details server-side.

        Args:
            error: The exception that occurred
            error_type: Type of error for categorization
            context: Additional context information
            user_id: User ID who encountered the error

        Returns:
            Dict with sanitized error message and error code
        """
        # Log full error details server-side
        logger = current_app.logger if current_app else logging.getLogger(__name__)

        log_message = f"Error occurred: {error_type}"
        if user_id:
            log_message += f" (user: {user_id})"
        if context:
            log_message += f" (context: {context})"

        logger.error(
            log_message,
            exc_info=True,
            extra={
                "error_type": error_type,
                "error_class": error.__class__.__name__,
                "context": context,
                "user_id": user_id,
            },
        )

        # Return sanitized user-facing response
        return {
            "error": cls.GENERIC_MESSAGES.get(
                error_type, cls.GENERIC_MESSAGES["unknown"]
            ),
            "error_code": cls.ERROR_CODES.get(error_type, cls.ERROR_CODES["unknown"]),
            "timestamp": cls._get_timestamp(),
        }

    @classmethod
    def log_sanitized_warning(
        cls,
        error: Exception,
        error_type: str = "unknown",
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
    ) -> str:
        """
        Create a sanitized log message that doesn't expose sensitive details.

        Args:
            error: The exception that occurred
            error_type: Type of error for categorization
            context: Additional context information
            user_id: User ID who encountered the error

        Returns:
            Sanitized log message string
        """
        logger = current_app.logger if current_app else logging.getLogger(__name__)

        # Log with sanitized message but full exception info
        sanitized_message = f"{error_type} error occurred"
        if user_id:
            sanitized_message += f" (user: {user_id})"
        if context:
            sanitized_message += (
                f" (context keys: {list(context.keys()) if context else []})"
            )

        logger.warning(
            sanitized_message,
            exc_info=True,
            extra={
                "error_type": error_type,
                "error_class": error.__class__.__name__,
                "context": context,
                "user_id": user_id,
            },
        )

        return sanitized_message

    @classmethod
    def categorize_error(cls, error: Exception) -> str:
        """
        Categorize error type based on exception class and message.

        Args:
            error: The exception to categorize

        Returns:
            Error type string
        """
        error_class = error.__class__.__name__.lower()
        error_message = str(error).lower()

        # Database errors
        if any(
            db_term in error_class
            for db_term in ["sql", "database", "integrity", "constraint"]
        ):
            return "database"

        # Validation errors
        if any(
            val_term in error_class for val_term in ["value", "type", "validation"]
        ) or any(
            val_term in error_message for val_term in ["invalid", "required", "missing"]
        ):
            return "validation"

        # File processing errors
        if any(
            file_term in error_class
            for file_term in ["file", "ioerror", "csv", "excel"]
        ) or any(
            file_term in error_message for file_term in ["file", "parse", "format"]
        ):
            return "file_processing"

        # Authentication errors
        if any(
            auth_term in error_class for auth_term in ["auth", "login", "unauthorized"]
        ):
            return "authentication"

        # Authorization errors
        if any(
            perm_term in error_class
            for perm_term in ["permission", "access", "forbidden"]
        ):
            return "authorization"

        # Network errors
        if any(
            net_term in error_class for net_term in ["connection", "network", "timeout"]
        ):
            return "network"

        return "unknown"

    @classmethod
    def _get_timestamp(cls) -> str:
        """Get current timestamp for error responses."""
        from datetime import datetime

        return datetime.utcnow().isoformat() + "Z"


def handle_import_error(
    error: Exception,
    operation: str = "import",
    context: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Specialized error handler for import operations.

    Args:
        error: The exception that occurred
        operation: Type of import operation
        context: Additional context information
        user_id: User ID who encountered the error

    Returns:
        Sanitized error response for import operations
    """
    error_type = ErrorSanitizer.categorize_error(error)

    # Use file_processing as default for import operations
    if error_type == "unknown":
        error_type = "file_processing"

    return ErrorSanitizer.sanitize_and_log(
        error=error,
        error_type=error_type,
        context={**{"operation": operation}, **(context or {})},
        user_id=user_id,
    )
