"""
Centralized legacy -> new endpoint mapping registry.

Consolidates LEGACY_ROUTE_MAP from all compat modules into one registry
for introspection, documentation, and deprecation tracking.

Usage::

    from app.compat.mapping_registry import register_routes, get_all_routes

    # In per-module compat file:
    register_routes("admin", LEGACY_ROUTE_MAP)

    # In admin/ops tooling:
    all_routes = get_all_routes()   # {"admin": {...}, "monitoring": {...}}
    flat = get_flat_routes()        # {"admin.index": {...}, "health.health_check": {...}}
"""

from typing import Any, Dict


_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_routes(module_name: str, routes: Dict[str, Any]) -> None:
    """Register legacy route mappings for a module.

    Args:
        module_name: The compat module name (e.g. "admin", "monitoring").
        routes: Dict mapping endpoint names to route metadata.
    """
    _REGISTRY[module_name] = routes


def get_all_routes() -> Dict[str, Dict[str, Any]]:
    """Get all registered legacy route mappings, grouped by module."""
    return dict(_REGISTRY)


def get_module_routes(module_name: str) -> Dict[str, Any]:
    """Get legacy route mappings for a specific module."""
    return _REGISTRY.get(module_name, {})


def get_flat_routes() -> Dict[str, Any]:
    """Get all routes as a flat dict (endpoint -> mapping)."""
    flat: Dict[str, Any] = {}
    for routes in _REGISTRY.values():
        flat.update(routes)
    return flat
