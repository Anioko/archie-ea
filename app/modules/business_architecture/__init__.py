"""Business Architecture module: the practice landing page.

A single front door to the twelve business-architecture outputs Archie already
serves. Every one of them was built and reachable; none of them had a shared
entry point, so an evaluating business architect concluded three of them did
not exist at all.

Self-contained, exposes register(app) — mirrors app/modules/organization.
Also registered from app/_bootstrap/blueprints.py::_register_optional_standalone
so it is never an unregistered blueprint.
"""

from .routes import business_architecture_bp


def register(app):
    """Register the Business Architecture blueprint on *app* (idempotent)."""
    if business_architecture_bp.name in app.blueprints:
        return
    app.register_blueprint(business_architecture_bp)


__all__ = ["register", "business_architecture_bp"]
