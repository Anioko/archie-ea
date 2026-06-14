"""
Solutions Strategic v2 — Guardrail-enabled thin wrapper over v1 module.

Strangler Fig migration from app/modules/solutions_strategic/ (v1).
Applies mark_blueprint_guardrailed() to all blueprints registered by the
v1 module, enabling guardrail detection and request-level timing.

Feature flag: USE_SOLUTIONS_STRATEGIC_V2
Fallback: v1 routes (unchanged)
Rollback: Set USE_SOLUTIONS_STRATEGIC_V2=false → v1 routes take over instantly.
"""

from flask import Flask


def register(app: Flask) -> None:
    """Register the solutions_strategic v2 module (inlined services and routes)."""
    from app.extensions import csrf
    from app.core.compat import mark_blueprint_guardrailed

    # Import all V2 blueprints
    from app.modules.solutions_strategic.v2.routes.roadmap_api import roadmap_bp
    from app.modules.solutions_strategic.v2.routes.strategic_routes import strategic_bp
    from app.modules.solutions_strategic.v2.routes.strategic_risks_hardened import (
        strategic_risks_bp,
    )
    from app.modules.solutions_strategic.v2.routes.solution_design_routes import (
        solution_design_bp,
    )
    from app.modules.solutions_strategic.v2.routes.roadmap_builder_routes import (
        roadmap_builder_bp,
    )
    from app.modules.solutions_strategic.v2.routes.solution_architect_routes import (
        solution_architect_bp,
    )
    from app.modules.solutions_strategic.v2.routes.solution_sad_routes import (
        solution_sad_bp,
    )
    from app.modules.solutions_strategic.v2.routes.solution_archimate_routes import (
        solution_archimate_bp,
    )
    from app.modules.solutions_strategic.v2.routes.solution_routes import (
        solutions_bp,
    )
    from app.modules.solutions_strategic.v2.routes.solution_composer_routes import (
        solution_composer_bp,
    )
    from app.modules.solutions_strategic.v2.routes.suggestion_api_routes import (
        api_bp as suggestion_api_bp,
    )
    from app.modules.solutions_strategic.v2.routes.solution_generate_routes import (
        solution_generate_bp,
    )
    from .routes.journey_v2_routes import architecture_journey_bp
    from .routes.integration_contract_routes import integration_contract_bp
    from .routes.governance_api_routes import governance_api_bp
    from app.modules.architecture_assistant.routes.wizard_ai_routes import wizard_ai_bp
    from .routes.solution_export_routes import solution_export_bp

    # Mark all blueprints as guardrailed BEFORE registration
    blueprints = [
        roadmap_bp, strategic_bp, strategic_risks_bp, solution_design_bp,
        roadmap_builder_bp, solution_architect_bp, solution_sad_bp,
        solution_archimate_bp, solutions_bp, solution_composer_bp,
        suggestion_api_bp, solution_generate_bp, architecture_journey_bp,
        integration_contract_bp, governance_api_bp, wizard_ai_bp,
        solution_export_bp,
    ]

    for bp in blueprints:
        mark_blueprint_guardrailed(bp)

    # Register all blueprints
    app.register_blueprint(roadmap_bp)
    app.register_blueprint(strategic_bp)
    app.register_blueprint(strategic_risks_bp)
    app.register_blueprint(solution_design_bp)
    app.register_blueprint(roadmap_builder_bp)
    app.register_blueprint(solution_architect_bp)
    app.register_blueprint(solution_sad_bp)
    app.register_blueprint(solution_archimate_bp)
    app.register_blueprint(solutions_bp)
    app.register_blueprint(solution_composer_bp)
    app.register_blueprint(suggestion_api_bp)
    app.register_blueprint(solution_generate_bp)
    app.register_blueprint(architecture_journey_bp)
    app.register_blueprint(integration_contract_bp)
    app.register_blueprint(governance_api_bp)
    app.register_blueprint(wizard_ai_bp)
    app.register_blueprint(solution_export_bp)

    # Permanent redirects: /journey_v2/* → /architecture-journey/*
    # Eliminates confusion from the internal variable name leaking into URLs
    from flask import redirect as _redirect

    @app.route('/journey_v2/', defaults={'path': ''})
    @app.route('/journey_v2/<path:path>')
    def _journey_v2_redirect(path):
        target = f'/architecture-journey/{path}' if path else '/architecture-journey/'
        return _redirect(target, 301)

    app.logger.info(
        "[MODULE-V2] solutions_strategic v2 registered (guardrail-enabled, ~260 routes, 14 blueprints)"
    )
