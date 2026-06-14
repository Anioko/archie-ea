"""
Query parameter validation for API endpoints.

Extracts and validates query parameters from ``request.args`` with type
coercion, defaults, and range checks.  Designed for new modular endpoints.

Usage::

    from app.core.validation.query import validate_query, QueryParam

    params, errors = validate_query(request.args, {
        "page": QueryParam(type=int, default=1, min_val=1),
        "per_page": QueryParam(type=int, default=25, min_val=1, max_val=100),
        "search": QueryParam(type=str, default="", max_length=500),
        "sort": QueryParam(type=str, choices=["name", "-name", "created_at"]),
    })
"""

from typing import Any, Dict, List, Optional, Tuple


class QueryParam:
    """Descriptor for a single query parameter."""

    def __init__(
        self,
        type: type = str,
        required: bool = False,
        default: Any = None,
        min_val: Optional[int] = None,
        max_val: Optional[int] = None,
        min_length: int = 0,
        max_length: int = 10_000,
        choices: Optional[List[Any]] = None,
        description: str = "",
    ):
        self.type = type
        self.required = required
        self.default = default
        self.min_val = min_val
        self.max_val = max_val
        self.min_length = min_length
        self.max_length = max_length
        self.choices = choices
        self.description = description

    def validate(self, raw: Optional[str], name: str) -> Tuple[Any, Optional[str]]:
        """Validate and coerce a raw query string value."""
        if raw is None or raw == "":
            if self.required:
                return None, f"Query parameter '{name}' is required"
            return self.default, None

        if self.type is int:
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return None, f"'{name}' must be an integer"
            if self.min_val is not None and value < self.min_val:
                return None, f"'{name}' must be >= {self.min_val}"
            if self.max_val is not None and value > self.max_val:
                return None, f"'{name}' must be <= {self.max_val}"
            return value, None

        if self.type is float:
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return None, f"'{name}' must be a number"
            if self.min_val is not None and value < self.min_val:
                return None, f"'{name}' must be >= {self.min_val}"
            if self.max_val is not None and value > self.max_val:
                return None, f"'{name}' must be <= {self.max_val}"
            return value, None

        if self.type is bool:
            if raw.lower() in ("true", "1", "yes"):
                return True, None
            if raw.lower() in ("false", "0", "no"):
                return False, None
            return None, f"'{name}' must be a boolean (true/false)"

        value = str(raw).strip()
        if len(value) < self.min_length:
            return None, f"'{name}' must be at least {self.min_length} characters"
        if len(value) > self.max_length:
            return None, f"'{name}' must be at most {self.max_length} characters"

        if self.choices and value not in self.choices:
            choices_str = ", ".join(repr(c) for c in self.choices[:10])
            return None, f"'{name}' must be one of: {choices_str}"

        return value, None


def validate_query(
    args: Dict[str, str],
    params: Dict[str, QueryParam],
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Validate query parameters against a param spec.

    Args:
        args: ``request.args`` or any string dict.
        params: Dict mapping param name to ``QueryParam`` descriptor.

    Returns:
        (clean_params, errors) — errors is empty dict on success.
    """
    clean = {}
    errors = {}

    for name, spec in params.items():
        raw = args.get(name)
        value, error = spec.validate(raw, name)
        if error:
            errors[name] = error
        else:
            clean[name] = value

    return clean, errors
