"""Organization module: enterprise org chart + enterprise RACI matrix.

A NEW, self-contained module. Exposes register(app) to attach
organization_bp — mirrors the pattern used by other standalone feature
blueprints registered from
app/_bootstrap/blueprints.py::_register_optional_standalone.
"""

from .routes import organization_bp


def register(app):
    """Register the Organization blueprint on *app* (idempotent)."""
    if organization_bp.name in app.blueprints:
        return
    app.register_blueprint(organization_bp)


__all__ = ["register", "organization_bp"]
