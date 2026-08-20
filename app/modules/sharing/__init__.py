"""Artefact sharing module (BA-B1).

Self-contained module exposing ``register(app)`` for
``app/_bootstrap/blueprints.py::_register_optional_standalone``, the same
pattern the Tech Radar module uses.
"""

from .routes import artefact_share_bp


def register(app):
    """Register the artefact-share blueprint on *app* (idempotent)."""
    if artefact_share_bp.name in app.blueprints:
        return
    app.register_blueprint(artefact_share_bp)


__all__ = ["register", "artefact_share_bp"]
