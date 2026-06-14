"""
Governance v2 — Guardrail-enabled thin wrapper over v1 module.

Strangler Fig migration from app/modules/governance/ (v1).
Applies mark_blueprint_guardrailed() to all blueprints registered by the
v1 module, enabling guardrail detection and request-level timing.

Feature flag: USE_GOVERNANCE_V2
Fallback: v1 routes (unchanged)
Rollback: Set USE_GOVERNANCE_V2=false → v1 routes take over instantly.
"""

from flask import Flask


def register(app: Flask) -> None:
    """Register the governance v2 module (guardrail-wrapped v1 blueprints)."""
    from app import csrf
    from app.core.compat import mark_blueprint_guardrailed

    # Import all V1 blueprints
    from app.modules.governance.routes.consolidation_list_routes import (
        consolidation_list_bp,
    )
    from app.modules.governance.routes.policy_monitoring_routes import (
        policy_monitoring_bp,
    )
    from app.modules.governance.routes.capability_management_routes import (
        capability_management,
    )
    from app.modules.governance.routes.capability_governance_routes import (
        capability_governance,
    )

    # Mark all blueprints as guardrailed BEFORE registration
    blueprints = [
        consolidation_list_bp,
        policy_monitoring_bp,
        capability_management,
        capability_governance,
    ]

    for bp in blueprints:
        mark_blueprint_guardrailed(bp)

    # Register all blueprints
    app.register_blueprint(consolidation_list_bp)
    app.register_blueprint(policy_monitoring_bp)
    app.register_blueprint(capability_management, url_prefix="/capability-management")
    app.register_blueprint(capability_governance, url_prefix="/capability-governance")

    app.logger.info(
        "[MODULE-V2] governance v2 registered (guardrail-enabled, 28 routes, 4 blueprints)"
    )
