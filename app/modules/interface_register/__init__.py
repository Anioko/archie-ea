"""Interface Register module (SAP S/4HANA Interface Register).

A self-contained module, modelled on app/modules/tech_radar/. Gives
ApplicationInterfaceMetadata its first producer: every interface is a real
ArchiMateElement (type='ApplicationInterface', layer='Application'),
scoped to a TechnologyRoadmapInitiative.

Exposes register(app) to attach interface_register_bp — mirrors the pattern
used by other standalone feature blueprints registered from
app/_bootstrap/blueprints.py::_register_optional_standalone.
"""

from .routes import interface_register_bp


def register(app):
    """Register the Interface Register blueprint on *app* (idempotent)."""
    if interface_register_bp.name in app.blueprints:
        return
    app.register_blueprint(interface_register_bp)


__all__ = ["register", "interface_register_bp"]
