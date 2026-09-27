"""Compatibility module for the retired Business Architecture directory."""

from .routes import business_architecture_bp


def register(app):
    """Register the compatibility redirect on *app* (idempotent)."""
    if business_architecture_bp.name in app.blueprints:
        return
    app.register_blueprint(business_architecture_bp)


__all__ = ["register", "business_architecture_bp"]
