"""
DEPRECATED: Import from app.modules.architecture.services instead.
-> app.modules.architecture.services.viewpoint_builder
Backward-compat re-export. Canonical: app/modules/architecture/services/viewpoint_builder.py
"""
from app.modules.architecture.services.viewpoint_builder import (  # noqa: F401
    ViewpointElement,
    ViewpointRelationship,
    Viewpoint,
    ViewpointValidationResult,
    ViewpointBuilder,
    get_viewpoint_builder,
)
