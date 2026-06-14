# DEPRECATED: Import from app.modules.architecture.services.archimate_validation_service instead.
"""Backward-compatibility shim. Canonical: app/modules/architecture/services/archimate_validation_service.py"""
from app.modules.architecture.services.archimate_validation_service import (  # noqa: F401,F403
    ArchiMateValidationService,
    validate_relationship,
    validate_and_log,
)
