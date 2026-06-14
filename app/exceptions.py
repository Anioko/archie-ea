"""
Production-Ready Exception System

Comprehensive exception hierarchy for user-friendly, actionable error handling.
All exceptions provide clear messages, recovery guidance, and proper logging.

Design Principles:
- User-friendly messages (no technical details exposed)
- Actionable guidance for recovery
- Proper HTTP status codes
- Structured logging context
- Security-conscious (no sensitive data in messages)
"""

from typing import Any, Dict, Optional, Union

# =============================================================================
# Base Exception Classes
# =============================================================================


class FlaskShadcnException(Exception):
    """Base exception for all Flask-Shadcn application errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        user_message: Optional[str] = None,
        recovery_action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        log_context: Optional[Dict[str, Any]] = None,
    ):
        self.message = message  # Technical message for logs
        self.user_message = user_message or message  # User-friendly message
        self.status_code = status_code
        self.error_code = error_code
        self.recovery_action = recovery_action  # What user should do
        self.details = details or {}  # Additional structured data
        self.log_context = log_context or {}  # Context for logging
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON API response."""
        response = {
            "success": False,
            "error": self.user_message,
            "error_code": self.error_code,
        }

        if self.recovery_action:
            response["recovery_action"] = self.recovery_action

        if self.details:
            response["details"] = self.details

        return response

    def to_log_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging (includes technical details)."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "user_message": self.user_message,
            "status_code": self.status_code,
            "details": self.details,
            "log_context": self.log_context,
        }


# =============================================================================
# Validation Errors (400)
# =============================================================================


class ValidationError(FlaskShadcnException):
    """Invalid input data or business rule violation."""

    def __init__(
        self,
        message: str = "Invalid data provided",
        user_message: str = "The data you provided is invalid. Please check your input and try again.",
        field: Optional[str] = None,
        validation_errors: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if field:
            details["field"] = field
        if validation_errors:
            details["validation_errors"] = validation_errors

        super().__init__(
            message=message,
            user_message=user_message,
            status_code=400,
            error_code=kwargs.pop("error_code", "VALIDATION_ERROR"),
            recovery_action=kwargs.pop("recovery_action", "Please correct the highlighted fields and submit again."),
            details=details,
            **kwargs,
        )


class MissingRequiredFieldError(ValidationError):
    """Required field is missing."""

    def __init__(self, field: str, **kwargs):
        super().__init__(
            message=f"Required field '{field}' is missing",
            user_message=f"The field '{field}' is required.",
            field=field,
            error_code="MISSING_REQUIRED_FIELD",
            recovery_action=f"Please provide a value for '{field}'.",
            **kwargs,
        )


class InvalidFormatError(ValidationError):
    """Data format is invalid."""

    def __init__(self, field: str, expected_format: str, **kwargs):
        super().__init__(
            message=f"Field '{field}' has invalid format (expected: {expected_format})",
            user_message=f"The format of '{field}' is invalid.",
            field=field,
            error_code="INVALID_FORMAT",
            recovery_action=f"Please ensure '{field}' matches the format: {expected_format}.",
            details={"expected_format": expected_format},
            **kwargs,
        )


class DuplicateEntryError(ValidationError):
    """Duplicate entry violates unique constraint."""

    def __init__(self, resource: str, field: str, value: str, **kwargs):
        super().__init__(
            message=f"Duplicate {resource}: {field}={value}",
            user_message=f"A {resource} with this {field} already exists.",
            error_code="DUPLICATE_ENTRY",
            recovery_action=f"Please use a different value for {field}.",
            details={"resource": resource, "field": field},
            **kwargs,
        )


# =============================================================================
# Authentication & Authorization Errors (401, 403)
# =============================================================================


class AuthenticationError(FlaskShadcnException):
    """User authentication failed or required."""

    def __init__(
        self,
        message: str = "Authentication required",
        user_message: str = "You need to log in to access this resource.",
        **kwargs,
    ):
        super().__init__(
            message=message,
            user_message=user_message,
            status_code=401,
            error_code="AUTHENTICATION_REQUIRED",
            recovery_action="Please log in and try again.",
            **kwargs,
        )


class InvalidCredentialsError(AuthenticationError):
    """Invalid username or password."""

    def __init__(self, **kwargs):
        super().__init__(
            message="Invalid credentials provided",
            user_message="Invalid username or password.",
            error_code="INVALID_CREDENTIALS",
            recovery_action="Please check your credentials and try again.",
            **kwargs,
        )


class SessionExpiredError(AuthenticationError):
    """User session has expired."""

    def __init__(self, **kwargs):
        super().__init__(
            message="User session expired",
            user_message="Your session has expired.",
            error_code="SESSION_EXPIRED",
            recovery_action="Please log in again.",
            **kwargs,
        )


class AuthorizationError(FlaskShadcnException):
    """User lacks required permissions."""

    def __init__(
        self,
        message: str = "Access denied",
        user_message: str = "You don't have permission to perform this action.",
        required_permission: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if required_permission:
            details["required_permission"] = required_permission

        super().__init__(
            message=message,
            user_message=user_message,
            status_code=403,
            error_code="FORBIDDEN",
            recovery_action="Please contact your administrator if you believe you should have access.",
            details=details,
            **kwargs,
        )


# =============================================================================
# Resource Errors (404, 409, 410)
# =============================================================================


class NotFoundError(FlaskShadcnException):
    """Requested resource not found."""

    def __init__(
        self,
        message: str = "Resource not found",
        user_message: str = "The resource you requested could not be found.",
        resource_type: Optional[str] = None,
        resource_id: Optional[Union[int, str]] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if resource_type:
            details["resource_type"] = resource_type
            user_message = f"The {resource_type} you requested could not be found."
        if resource_id:
            details["resource_id"] = str(resource_id)

        super().__init__(
            message=message,
            user_message=user_message,
            status_code=404,
            error_code="NOT_FOUND",
            recovery_action="Please check the ID and try again, or browse to find the resource.",
            details=details,
            **kwargs,
        )


class ConflictError(FlaskShadcnException):
    """Request conflicts with current state."""

    def __init__(
        self,
        message: str = "Request conflicts with current state",
        user_message: str = "This action conflicts with the current state of the resource.",
        **kwargs,
    ):
        super().__init__(
            message=message,
            user_message=user_message,
            status_code=409,
            error_code="CONFLICT",
            recovery_action="Please refresh the page and try again.",
            **kwargs,
        )


class ResourceGoneError(FlaskShadcnException):
    """Resource has been permanently deleted."""

    def __init__(
        self,
        message: str = "Resource has been deleted",
        user_message: str = "This resource is no longer available.",
        **kwargs,
    ):
        super().__init__(
            message=message,
            user_message=user_message,
            status_code=410,
            error_code="GONE",
            recovery_action="This resource has been permanently removed.",
            **kwargs,
        )


# =============================================================================
# Rate Limiting & Throttling (429)
# =============================================================================


class RateLimitError(FlaskShadcnException):
    """Rate limit exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        user_message: str = "You've made too many requests. Please wait and try again.",
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if retry_after:
            details["retry_after"] = retry_after
            user_message = f"Too many requests. Please wait {retry_after} seconds and try again."

        super().__init__(
            message=message,
            user_message=user_message,
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            recovery_action=f"Please wait {retry_after or 'a moment'} before trying again.",
            details=details,
            **kwargs,
        )


# =============================================================================
# Database Errors (500)
# =============================================================================


class DatabaseError(FlaskShadcnException):
    """Database operation failed."""

    def __init__(
        self,
        message: str = "Database operation failed",
        user_message: str = "We're experiencing technical difficulties. Please try again.",
        operation: Optional[str] = None,
        retry: bool = True,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if operation:
            details["operation"] = operation
        details["retry"] = retry
        recovery = kwargs.pop(
            "recovery_action",
            "Please try again in a moment. If the problem persists, contact support.",
        )

        super().__init__(
            message=message,
            user_message=user_message,
            status_code=500,
            error_code="DATABASE_ERROR",
            recovery_action=recovery,
            details=details,
            **kwargs,
        )


class ConnectionError(DatabaseError):
    """Database connection failed."""

    def __init__(self, **kwargs):
        super().__init__(
            message="Database connection failed",
            user_message="Unable to connect to the database. Please try again.",
            error_code="DATABASE_CONNECTION_ERROR",
            retry=True,
            **kwargs,
        )


class IntegrityError(DatabaseError):
    """Database integrity constraint violated."""

    def __init__(self, constraint: Optional[str] = None, **kwargs):
        super().__init__(
            message=f"Database integrity violation: {constraint}"
            if constraint
            else "Database integrity violation",
            user_message="This operation would violate data integrity rules.",
            error_code="DATABASE_INTEGRITY_ERROR",
            retry=False,
            details={"constraint": constraint} if constraint else {},
            **kwargs,
        )


# =============================================================================
# External Service Errors (500, 503)
# =============================================================================


class ExternalServiceError(FlaskShadcnException):
    """External service or API failed."""

    def __init__(
        self,
        message: str = "External service error",
        user_message: str = "An external service is temporarily unavailable.",
        service_name: Optional[str] = None,
        retry: bool = True,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if service_name:
            details["service"] = service_name
            user_message = f"The {service_name} service is temporarily unavailable."
        details["retry"] = retry
        recovery = kwargs.pop("recovery_action", "Please try again in a few moments.")

        super().__init__(
            message=message,
            user_message=user_message,
            status_code=503,
            error_code="SERVICE_UNAVAILABLE",
            recovery_action=recovery,
            details=details,
            **kwargs,
        )


class AIServiceError(ExternalServiceError):
    """AI/LLM service error."""

    def __init__(
        self,
        message: str = "AI service error",
        user_message: str = "The AI service is temporarily unavailable.",
        **kwargs,
    ):
        super().__init__(
            message=message,
            user_message=user_message,
            service_name="AI",
            error_code="AI_SERVICE_ERROR",
            **kwargs,
        )


class VendorAPIError(ExternalServiceError):
    """Vendor API error."""

    def __init__(
        self,
        vendor: str,
        message: str = "Vendor API error",
        user_message: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            user_message=user_message or f"Unable to connect to {vendor} API.",
            service_name=vendor,
            error_code="VENDOR_API_ERROR",
            **kwargs,
        )


# =============================================================================
# Business Logic Errors (422)
# =============================================================================


class BusinessRuleError(FlaskShadcnException):
    """Business rule or logic violation."""

    def __init__(
        self,
        message: str = "Business rule violation",
        user_message: str = "This action violates business rules.",
        rule_name: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if rule_name:
            details["rule"] = rule_name
        recovery = kwargs.pop(
            "recovery_action", "Please review the business rules and adjust your action."
        )

        super().__init__(
            message=message,
            user_message=user_message,
            status_code=422,
            error_code="BUSINESS_RULE_VIOLATION",
            recovery_action=recovery,
            details=details,
            **kwargs,
        )


class WorkflowError(BusinessRuleError):
    """Workflow state transition error."""

    def __init__(self, current_state: str, attempted_transition: str, **kwargs):
        super().__init__(
            message=f"Invalid workflow transition from {current_state} to {attempted_transition}",
            user_message=f"Cannot transition from {current_state} to {attempted_transition}.",
            error_code="WORKFLOW_ERROR",
            details={"current_state": current_state, "attempted_transition": attempted_transition},
            **kwargs,
        )


# =============================================================================
# Configuration & System Errors (500)
# =============================================================================


class ConfigurationError(FlaskShadcnException):
    """System configuration error."""

    def __init__(
        self,
        message: str = "System configuration error",
        user_message: str = "The system is not properly configured. Please contact support.",
        config_key: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if config_key:
            details["config_key"] = config_key

        super().__init__(
            message=message,
            user_message=user_message,
            status_code=500,
            error_code="CONFIGURATION_ERROR",
            recovery_action="Please contact your system administrator.",
            details=details,
            **kwargs,
        )


class TimeoutError(FlaskShadcnException):
    """Operation timed out."""

    def __init__(
        self,
        message: str = "Operation timed out",
        user_message: str = "The operation took too long and was cancelled.",
        operation: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if operation:
            details["operation"] = operation
        if timeout_seconds:
            details["timeout"] = timeout_seconds

        super().__init__(
            message=message,
            user_message=user_message,
            status_code=504,
            error_code="TIMEOUT",
            recovery_action="Please try again or break the operation into smaller parts.",
            details=details,
            **kwargs,
        )
