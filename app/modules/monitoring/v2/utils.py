"""
Monitoring v2 utilities.

Helper functions shared across v2 health and metrics routes.
"""

from typing import Any, Dict, Tuple

from app.core.api import api_error, api_success


def health_result_to_response(result: Dict[str, Any]) -> Tuple:
    """Convert a HealthService result dict to a standardized API response.

    Args:
        result: Dict with at least a ``status`` key.

    Returns:
        (flask_response, status_code) tuple.
    """
    status = result.get("status", "unknown")
    if status == "unhealthy":
        return api_error(
            result.get("message", "Component unhealthy"),
            status_code=503,
            errors={"status": status},
        )
    return api_success(result, status_code=200)


def is_critical_component(component_name: str) -> bool:
    """Return True if *component_name* is a critical health component.

    Critical components cause the overall status to become 'unhealthy'
    when they fail (database, storage). Non-critical components cause
    'degraded' status (LLM, cache).
    """
    return component_name in ("database", "storage")
