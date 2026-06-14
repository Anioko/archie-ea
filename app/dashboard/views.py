"""
DEPRECATED: Import from app.modules.dashboard.routes.dashboard_views instead.
-> app.modules.dashboard.routes.dashboard_views
Backward-compat re-export. Canonical: app/modules/dashboard/routes/dashboard_views.py
"""
from app.modules.dashboard.routes.dashboard_views import (  # noqa: F401
    dashboard_bp,
)

# Legacy alias — bootstrap imports "dashboard" by name
dashboard = dashboard_bp  # noqa: F401
