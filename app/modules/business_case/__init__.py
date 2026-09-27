"""Business Case module.

A NEW, self-contained module consolidating business-case data (today
scattered across strategic-initiative budgets, capability cost
allocations, and value elements) into a single artifact a Business
Architect can assemble and review.

Exposes register(app) to attach business_case_bp — mirrors the pattern
used by other standalone feature blueprints registered from
app/_bootstrap/blueprints.py::_register_optional_standalone (see e.g.
app/modules/business_model_canvas).
"""

from .routes import business_case_bp


def register(app):
    """Register the Business Case blueprint on *app* (idempotent)."""
    if business_case_bp.name in app.blueprints:
        return
    app.register_blueprint(business_case_bp)


__all__ = ["register", "business_case_bp"]
