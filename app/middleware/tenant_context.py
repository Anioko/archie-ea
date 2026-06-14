"""
Tenant context middleware — sets g.current_org_id on every request.

Reads the authenticated user's organization_id and puts it on Flask's g
object so that the tenant isolation event listener can pick it up.

For unauthenticated requests, g.current_org_id stays None and the event
listener becomes a no-op (all data visible — used for login page, health
check, public APIs).
"""

import logging

from flask import g
from flask_login import current_user

logger = logging.getLogger(__name__)


def install_tenant_context(app):
    """Register before_request handler that sets g.current_org_id."""

    @app.before_request
    def set_tenant_context():
        if current_user.is_authenticated and hasattr(current_user, "organization_id"):
            g.current_org_id = current_user.organization_id
            g.current_org = getattr(current_user, "organization", None)
        else:
            g.current_org_id = None
            g.current_org = None
