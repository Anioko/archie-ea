"""Tech Radar module (ARCH-124).

A NEW, self-contained module. Exposes register(app) to attach
tech_radar_bp — mirrors the pattern used by other standalone feature
blueprints registered from
app/_bootstrap/blueprints.py::_register_optional_standalone.
"""

from .routes import tech_radar_bp


def register(app):
    """Register the Tech Radar blueprint on *app* (idempotent)."""
    if tech_radar_bp.name in app.blueprints:
        return
    app.register_blueprint(tech_radar_bp)


__all__ = ["register", "tech_radar_bp"]
