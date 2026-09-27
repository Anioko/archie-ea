"""Business Model Canvas + Operating Model module.

A NEW, self-contained module (Business-Architect signature artifact).
Exposes register(app) to attach business_model_bp — mirrors the pattern
used by other standalone feature blueprints registered from
app/_bootstrap/blueprints.py::_register_optional_standalone.
"""

from .routes import business_model_bp


def register(app):
    """Register the Business Model Canvas blueprint on *app* (idempotent)."""
    if business_model_bp.name in app.blueprints:
        return
    app.register_blueprint(business_model_bp)


__all__ = ["register", "business_model_bp"]
