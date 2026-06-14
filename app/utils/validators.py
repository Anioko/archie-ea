"""
Input Validation Utilities for API Endpoints

Provides comprehensive input validation to prevent security issues
including XSS, injection attacks, and data integrity problems.
"""

import html
import re
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple, Union

from flask import jsonify, request


class ValidationError(Exception):
    """Custom exception for validation errors."""

    def __init__(self, message: str, field: str = None, code: str = "VALIDATION_ERROR"):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(message)


def validate_string(
    value: Any,
    max_length: int = 255,
    field_name: str = "field",
    min_length: int = 0,
    required: bool = False,
    allow_none: bool = True,
    pattern: str = None,
    strip_whitespace: bool = True,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate string inputs with configurable constraints.

    Args:
        value: The value to validate
        max_length: Maximum allowed string length (default: 255)
        field_name: Name of the field for error messages
        min_length: Minimum required string length (default: 0)
        required: Whether the field is required
        allow_none: Whether None values are allowed (when not required)
        pattern: Optional regex pattern to match
        strip_whitespace: Whether to strip leading/trailing whitespace

    Returns:
        Tuple of (is_valid, sanitized_value, error_message)
    """
    # Handle None values
    if value is None:
        if required:
            return False, None, f"{field_name} is required"
        if allow_none:
            return True, None, None
        return False, None, f"{field_name} cannot be null"

    # Ensure value is string
    if not isinstance(value, str):
        try:
            value = str(value)
        except (TypeError, ValueError):
            return False, None, f"{field_name} must be a string"

    # Strip whitespace if configured
    if strip_whitespace:
        value = value.strip()

    # Check for empty string when required
    if required and not value:
        return False, None, f"{field_name} is required"

    # Check minimum length
    if len(value) < min_length:
        return False, None, f"{field_name} must be at least {min_length} characters"

    # Check maximum length
    if len(value) > max_length:
        return False, None, f"{field_name} must not exceed {max_length} characters"

    # Check pattern if provided
    if pattern and value:
        if not re.match(pattern, value):
            return False, None, f"{field_name} format is invalid"

    return True, value, None


def validate_integer(
    value: Any,
    min_val: int = None,
    max_val: int = None,
    field_name: str = "field",
    required: bool = False,
    allow_none: bool = True,
) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Validate integer inputs with configurable constraints.

    Args:
        value: The value to validate
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        field_name: Name of the field for error messages
        required: Whether the field is required
        allow_none: Whether None values are allowed (when not required)

    Returns:
        Tuple of (is_valid, validated_value, error_message)
    """
    # Handle None values
    if value is None or value == "":
        if required:
            return False, None, f"{field_name} is required"
        if allow_none:
            return True, None, None
        return False, None, f"{field_name} cannot be null"

    # Convert to integer
    try:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                if required:
                    return False, None, f"{field_name} is required"
                return True, None, None
        int_value = int(value)
    except (TypeError, ValueError):
        return False, None, f"{field_name} must be a valid integer"

    # Check minimum value
    if min_val is not None and int_value < min_val:
        return False, None, f"{field_name} must be at least {min_val}"

    # Check maximum value
    if max_val is not None and int_value > max_val:
        return False, None, f"{field_name} must not exceed {max_val}"

    return True, int_value, None


def validate_float(
    value: Any,
    min_val: float = None,
    max_val: float = None,
    field_name: str = "field",
    required: bool = False,
    allow_none: bool = True,
    decimal_places: int = None,
) -> Tuple[bool, Optional[float], Optional[str]]:
    """
    Validate float/decimal inputs with configurable constraints.

    Args:
        value: The value to validate
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        field_name: Name of the field for error messages
        required: Whether the field is required
        allow_none: Whether None values are allowed
        decimal_places: Maximum decimal places allowed

    Returns:
        Tuple of (is_valid, validated_value, error_message)
    """
    # Handle None values
    if value is None or value == "":
        if required:
            return False, None, f"{field_name} is required"
        if allow_none:
            return True, None, None
        return False, None, f"{field_name} cannot be null"

    # Convert to float
    try:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                if required:
                    return False, None, f"{field_name} is required"
                return True, None, None
        float_value = float(value)
    except (TypeError, ValueError):
        return False, None, f"{field_name} must be a valid number"

    # Check for NaN and infinity
    import math

    if math.isnan(float_value) or math.isinf(float_value):
        return False, None, f"{field_name} must be a finite number"

    # Check minimum value
    if min_val is not None and float_value < min_val:
        return False, None, f"{field_name} must be at least {min_val}"

    # Check maximum value
    if max_val is not None and float_value > max_val:
        return False, None, f"{field_name} must not exceed {max_val}"

    # Round to decimal places if specified
    if decimal_places is not None:
        float_value = round(float_value, decimal_places)

    return True, float_value, None


def validate_email(
    value: Any, field_name: str = "email", required: bool = False
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate email format using RFC 5322 compliant pattern.

    Args:
        value: The email value to validate
        field_name: Name of the field for error messages
        required: Whether the field is required

    Returns:
        Tuple of (is_valid, sanitized_email, error_message)
    """
    if value is None or value == "":
        if required:
            return False, None, f"{field_name} is required"
        return True, None, None

    if not isinstance(value, str):
        return False, None, f"{field_name} must be a string"

    email = value.strip().lower()

    if not email:
        if required:
            return False, None, f"{field_name} is required"
        return True, None, None

    # RFC 5322 compliant email pattern (simplified but robust)
    email_pattern = r"^[a-zA-Z0 - 9._%+-]+@[a-zA-Z0 - 9.-]+\.[a-zA-Z]{2,}$"

    if not re.match(email_pattern, email):
        return False, None, f"{field_name} must be a valid email address"

    # Additional checks
    if len(email) > 254:  # RFC 5321 limit
        return False, None, f"{field_name} is too long"

    local_part, domain = email.rsplit("@", 1)
    if len(local_part) > 64:  # RFC 5321 limit
        return False, None, f"{field_name} local part is too long"

    return True, email, None


def validate_url(
    value: Any, field_name: str = "url", required: bool = False, allowed_schemes: List[str] = None
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate URL format.

    Args:
        value: The URL value to validate
        field_name: Name of the field for error messages
        required: Whether the field is required
        allowed_schemes: List of allowed URL schemes (default: http, https)

    Returns:
        Tuple of (is_valid, sanitized_url, error_message)
    """
    if allowed_schemes is None:
        allowed_schemes = ["http", "https"]

    if value is None or value == "":
        if required:
            return False, None, f"{field_name} is required"
        return True, None, None

    if not isinstance(value, str):
        return False, None, f"{field_name} must be a string"

    url = value.strip()

    if not url:
        if required:
            return False, None, f"{field_name} is required"
        return True, None, None

    # Basic URL pattern
    url_pattern = r"^(https?|ftp)://[^\s/$.?#].[^\s]*$"

    if not re.match(url_pattern, url, re.IGNORECASE):
        return False, None, f"{field_name} must be a valid URL"

    # Check scheme
    scheme = url.split("://")[0].lower()
    if scheme not in allowed_schemes:
        return (
            False,
            None,
            f"{field_name} must use one of these schemes: {', '.join(allowed_schemes)}",
        )

    # Check length
    if len(url) > 2048:
        return False, None, f"{field_name} is too long"

    return True, url, None


def validate_json_payload(
    data: Any,
    required_fields: List[str] = None,
    optional_fields: List[str] = None,
    field_validators: Dict[str, callable] = None,
    allow_extra_fields: bool = True,
) -> Tuple[bool, Dict[str, Any], List[Dict[str, str]]]:
    """
    Validate JSON request payload with field-level validation.

    Args:
        data: The JSON data to validate (dict expected)
        required_fields: List of required field names
        optional_fields: List of optional field names
        field_validators: Dict mapping field names to validator functions
        allow_extra_fields: Whether to allow fields not in required/optional lists

    Returns:
        Tuple of (is_valid, validated_data, list_of_errors)

    Example:
        valid, data, errors = validate_json_payload(
            request.get_json(),
            required_fields=['name', 'email'],
            optional_fields=['phone'],
            field_validators={
                'name': lambda v: validate_string(v, max_length=100, field_name='name', required=True),
                'email': lambda v: validate_email(v, required=True),
            }
        )
    """
    required_fields = required_fields or []
    optional_fields = optional_fields or []
    field_validators = field_validators or {}

    errors = []
    validated_data = {}

    # Check if data is a dict
    if data is None:
        errors.append({"field": "body", "message": "Request body is required"})
        return False, {}, errors

    if not isinstance(data, dict):
        errors.append({"field": "body", "message": "Request body must be a JSON object"})
        return False, {}, errors

    # Check required fields
    for field in required_fields:
        if field not in data:
            errors.append({"field": field, "message": f"{field} is required"})

    # Validate fields with custom validators
    all_known_fields = set(required_fields + optional_fields)

    for field, value in data.items():
        # Check for extra fields
        if not allow_extra_fields and field not in all_known_fields:
            errors.append({"field": field, "message": f"Unknown field: {field}"})
            continue

        # Apply field-specific validator if exists
        if field in field_validators:
            validator = field_validators[field]
            is_valid, validated_value, error_msg = validator(value)
            if not is_valid:
                errors.append({"field": field, "message": error_msg})
            else:
                validated_data[field] = validated_value
        else:
            validated_data[field] = value

    return len(errors) == 0, validated_data, errors


def validate_list(
    value: Any,
    field_name: str = "field",
    required: bool = False,
    min_items: int = 0,
    max_items: int = None,
    item_validator: callable = None,
) -> Tuple[bool, Optional[List], Optional[str]]:
    """
    Validate list/array inputs.

    Args:
        value: The value to validate
        field_name: Name of the field for error messages
        required: Whether the field is required
        min_items: Minimum number of items required
        max_items: Maximum number of items allowed
        item_validator: Function to validate each item

    Returns:
        Tuple of (is_valid, validated_list, error_message)
    """
    if value is None:
        if required:
            return False, None, f"{field_name} is required"
        return True, None, None

    if not isinstance(value, list):
        return False, None, f"{field_name} must be a list"

    if len(value) < min_items:
        return False, None, f"{field_name} must have at least {min_items} items"

    if max_items is not None and len(value) > max_items:
        return False, None, f"{field_name} must not have more than {max_items} items"

    if item_validator:
        validated_items = []
        for i, item in enumerate(value):
            is_valid, validated_item, error_msg = item_validator(item)
            if not is_valid:
                return False, None, f"{field_name}[{i}]: {error_msg}"
            validated_items.append(validated_item)
        return True, validated_items, None

    return True, value, None


def validate_enum(
    value: Any,
    allowed_values: List[Any],
    field_name: str = "field",
    required: bool = False,
    case_insensitive: bool = False,
) -> Tuple[bool, Optional[Any], Optional[str]]:
    """
    Validate that value is one of allowed values.

    Args:
        value: The value to validate
        allowed_values: List of allowed values
        field_name: Name of the field for error messages
        required: Whether the field is required
        case_insensitive: Whether string comparison should be case-insensitive

    Returns:
        Tuple of (is_valid, validated_value, error_message)
    """
    if value is None or value == "":
        if required:
            return False, None, f"{field_name} is required"
        return True, None, None

    check_value = value
    check_allowed = allowed_values

    if case_insensitive and isinstance(value, str):
        check_value = value.lower()
        check_allowed = [v.lower() if isinstance(v, str) else v for v in allowed_values]

    if check_value not in check_allowed:
        allowed_str = ", ".join(str(v) for v in allowed_values)
        return False, None, f"{field_name} must be one of: {allowed_str}"

    return True, value, None


def sanitize_html(value: str, allow_basic_formatting: bool = False) -> str:
    """
    Strip dangerous HTML/scripts from input to prevent XSS attacks.

    Args:
        value: The string to sanitize
        allow_basic_formatting: Whether to allow basic HTML tags (b, i, u, em, strong, br)

    Returns:
        Sanitized string with dangerous content removed
    """
    if value is None:
        return None

    if not isinstance(value, str):
        value = str(value)

    # First, escape all HTML entities
    sanitized = html.escape(value)

    if allow_basic_formatting:
        # Restore safe tags after escaping
        safe_tags = ["b", "i", "u", "em", "strong", "br", "p"]
        for tag in safe_tags:
            # Restore opening tags
            sanitized = sanitized.replace(f"&lt;{tag}&gt;", f"<{tag}>")
            sanitized = sanitized.replace(f"&lt;{tag.upper()}&gt;", f"<{tag}>")
            # Restore closing tags
            sanitized = sanitized.replace(f"&lt;/{tag}&gt;", f"</{tag}>")
            sanitized = sanitized.replace(f"&lt;/{tag.upper()}&gt;", f"</{tag}>")
            # Restore self-closing tags
            sanitized = sanitized.replace(f"&lt;{tag}/&gt;", f"<{tag}/>")
            sanitized = sanitized.replace(f"&lt;{tag} /&gt;", f"<{tag} />")

    return sanitized


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename to prevent directory traversal and other attacks.

    Args:
        filename: The filename to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized filename
    """
    if not filename:
        return ""

    # Remove any path separators
    filename = filename.replace("/", "").replace("\\", "")

    # Remove any null bytes
    filename = filename.replace("\x00", "")

    # Remove leading/trailing dots and spaces
    filename = filename.strip(". ")

    # Remove or replace dangerous characters
    dangerous_chars = '<>:"|?*'
    for char in dangerous_chars:
        filename = filename.replace(char, "_")

    # Truncate to max length
    if len(filename) > max_length:
        # Preserve extension if possible
        if "." in filename:
            name, ext = filename.rsplit(".", 1)
            max_name_len = max_length - len(ext) - 1
            if max_name_len > 0:
                filename = name[:max_name_len] + "." + ext
            else:
                filename = filename[:max_length]
        else:
            filename = filename[:max_length]

    return filename


def validation_error_response(errors: Union[str, List[Dict]], message: str = "Validation failed"):
    """
    Create a standardized validation error response.

    Args:
        errors: Error message string or list of error dicts
        message: Overall error message

    Returns:
        Tuple of (jsonified_response, 400)
    """
    if isinstance(errors, str):
        errors = [{"field": "general", "message": errors}]

    return (
        jsonify(
            {
                "success": False,
                "error": {"code": "VALIDATION_ERROR", "message": message, "details": errors},
            }
        ),
        400,
    )


def require_json(f):
    """
    Decorator to require JSON content type for POST/PUT/PATCH requests.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ["POST", "PUT", "PATCH"]:
            if not request.is_json and request.content_type != "application/json":
                # Allow form data for specific endpoints
                if not request.form and not request.files:
                    return validation_error_response(
                        "Content-Type must be application/json", "Invalid content type"
                    )
        return f(*args, **kwargs)

    return decorated_function


def validate_request(
    required_fields: List[str] = None,
    optional_fields: List[str] = None,
    field_validators: Dict[str, callable] = None,
):
    """
    Decorator to validate JSON request payload.

    Usage:
        @validate_request(
            required_fields=['name', 'email'],
            field_validators={
                'name': lambda v: validate_string(v, max_length=100, required=True),
                'email': lambda v: validate_email(v, required=True),
            }
        )
        def my_endpoint():
            # request.validated_data contains validated data
            pass
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.method in ["POST", "PUT", "PATCH"] and request.is_json:
                data = request.get_json(silent=True)
                is_valid, validated_data, errors = validate_json_payload(
                    data,
                    required_fields=required_fields,
                    optional_fields=optional_fields,
                    field_validators=field_validators,
                )
                if not is_valid:
                    return validation_error_response(errors)
                request.validated_data = validated_data
            return f(*args, **kwargs)

        return decorated_function

    return decorator


# Common validation patterns
PATTERNS = {
    "alphanumeric": r"^[a-zA-Z0 - 9]+$",
    "alphanumeric_space": r"^[a-zA-Z0 - 9\s]+$",
    "alphanumeric_underscore": r"^[a-zA-Z0 - 9_]+$",
    "slug": r"^[a-z0 - 9]+(?:-[a-z0 - 9]+)*$",
    "uuid": r"^[0 - 9a-f]{8}-[0 - 9a-f]{4}-[0 - 9a-f]{4}-[0 - 9a-f]{4}-[0 - 9a-f]{12}$",
    "phone": r"^\+?[1 - 9]\d{1,14}$",
    "date_iso": r"^\d{4}-\d{2}-\d{2}$",
    "datetime_iso": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
}


# Pre-configured validators for common use cases
def validate_application_name(value):
    """Validate application name field."""
    return validate_string(value, max_length=255, min_length=1, field_name="name", required=True)


def validate_description(value, required=False):
    """Validate description field."""
    return validate_string(value, max_length=5000, field_name="description", required=required)


def validate_chat_message(value):
    """Validate chat message content."""
    is_valid, sanitized, error = validate_string(
        value, max_length=10000, min_length=1, field_name="message", required=True
    )
    if is_valid and sanitized:
        # Additional sanitization for chat messages
        sanitized = sanitize_html(sanitized)
    return is_valid, sanitized, error


def validate_id(value, field_name="id"):
    """Validate ID field (positive integer)."""
    return validate_integer(value, min_val=1, field_name=field_name, required=True)
