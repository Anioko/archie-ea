"""
DEPRECATED: Import from app.modules.capabilities.services instead.
-> app.modules.capabilities.services.capability_service

Backward-compat re-export. Canonical: app/modules/capabilities/services/capability_taxonomy_service.py
"""

from app.modules.capabilities.services.capability_taxonomy_service import (  # noqa: F401
    CapabilityTaxonomyService,
    ValidationResult,
    ValidationViolation,
)
