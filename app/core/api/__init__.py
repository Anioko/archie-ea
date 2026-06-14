"""
Core API utilities.

Provides standardized response format and pagination for all API endpoints.

Usage::

    from app.core.api import api_success, api_error, api_paginated
    from app.core.api.pagination import get_pagination_params
"""

from .pagination import get_pagination_dict, get_pagination_params
from .response import api_error, api_paginated, api_success

__all__ = [
    "api_success",
    "api_error",
    "api_paginated",
    "get_pagination_params",
    "get_pagination_dict",
]
