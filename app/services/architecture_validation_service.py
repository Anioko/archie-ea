# DEPRECATED: Import from app.modules.architecture.services.architecture_validation_service instead.
"""Backward-compatibility shim. Canonical: app/modules/architecture/services/architecture_validation_service.py"""
from app.modules.architecture.services.architecture_validation_service import (  # noqa: F401,F403
    VALID_ELEMENT_TYPES,
    VALID_LAYERS,
    VALID_RELATIONSHIP_TYPES,
    ArchitectureValidator,
)
