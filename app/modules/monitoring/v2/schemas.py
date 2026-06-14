"""
Validation schemas for monitoring v2 endpoints.

Currently monitoring endpoints are all GET with no request body,
so schemas here are minimal. This file exists as the canonical
location for any future POST/PUT monitoring endpoints (e.g.
custom health check registration, alert configuration).
"""

from app.core.validation.schemas import EnumField, IntField, Schema, StringField


class HealthFilterSchema(Schema):
    """Optional query-parameter schema for filtering health check components."""
    component = EnumField(
        choices=["database", "storage", "cache", "llm", "external", "vendors"],
        required=False,
        default=None,
        description="Filter to a single component",
    )
    timeout = IntField(
        required=False,
        default=5,
        min_val=1,
        max_val=30,
        description="Health check timeout in seconds",
    )
