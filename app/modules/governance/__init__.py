"""
Governance module -- Centralized governance blueprint registration.

Consolidates registration of 4 governance-related blueprints behind a single
feature flag (USE_NEW_GOVERNANCE).

Migrated from:
- app/routes/capability_governance_routes.py   (6 routes, "capability_governance" blueprint)
- app/routes/capability_management_routes.py   (7 routes, "capability_management" blueprint)
- app/routes/policy_monitoring_routes.py       (7 routes, "policy_monitoring" blueprint)
- app/routes/consolidation_list_routes.py      (8 routes, "consolidation_list" blueprint)

Total: 28 routes across 4 blueprints.
"""
import logging

from flask import Flask

from app.extensions import db  # noqa: F401 — re-exported for submodule imports

logger = logging.getLogger(__name__)


def register(app: Flask) -> None:
    from app import csrf

    # --- 1. Consolidation List ---
    from app.modules.governance.routes.consolidation_list_routes import consolidation_list_bp

    app.register_blueprint(consolidation_list_bp)

    # --- 2. Policy Monitoring ---
    from app.modules.governance.routes.policy_monitoring_routes import policy_monitoring_bp

    app.register_blueprint(policy_monitoring_bp)

    # --- 3. Capability Management ---
    from app.modules.governance.routes.capability_management_routes import capability_management

    app.register_blueprint(capability_management, url_prefix="/capability-management")

    # --- 4. Capability Governance ---
    from app.modules.governance.routes.capability_governance_routes import capability_governance

    app.register_blueprint(capability_governance, url_prefix="/capability-governance")

    # --- 5. Governance Dashboard (North Star) ---
    from app.modules.governance.routes.governance_dashboard_routes import governance_bp

    app.register_blueprint(governance_bp)

    app.logger.info(
        "[MODULE] governance registered (39 routes, 5 blueprints)"
    )
