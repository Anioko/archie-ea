"""
DEPRECATED: Import from app.modules.account.routes.account_routes instead.
-> app.modules.account.routes.account_routes
Backward-compat re-export. Canonical: app/modules/account/routes/account_routes.py
"""
from app.modules.account.routes.account_routes import (  # noqa: F401
    account_bp,
)

# Legacy alias — app/account/__init__.py imports "account" by name
account = account_bp  # noqa: F401
