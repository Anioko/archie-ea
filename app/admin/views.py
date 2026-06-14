"""
DEPRECATED: Import from app.modules.admin.routes.admin_routes instead.
-> app.modules.admin.routes.admin_routes
Backward-compat re-export. Canonical: app/modules/admin/routes/admin_routes.py
"""
from app.modules.admin.routes.admin_routes import (  # noqa: F401
    admin_bp,
)

# Legacy alias — app/admin/__init__.py imports "admin" by name
admin = admin_bp  # noqa: F401
