"""Admin v2 route blueprints."""

from .admin_routes import admin_bp_v2
from .sidebar_mgmt_routes import sidebar_mgmt_bp_v2
from .deprecation_routes import deprecation_bp_v2

__all__ = ["admin_bp_v2", "sidebar_mgmt_bp_v2", "deprecation_bp_v2"]
