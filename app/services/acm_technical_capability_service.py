"""
DEPRECATED: Import from app.modules.capabilities.services instead.
-> app.modules.capabilities.services.seeder_service

Backward-compat re-export. Canonical: app/modules/capabilities/services/acm_technical_capability_service.py
"""

from app.models.technical_capability import (  # noqa: F401
    TechnicalCapability,
    application_technical_capability_mapping,
    technical_capability_business_mapping,
)
from app.modules.capabilities.services.acm_technical_capability_service import (  # noqa: F401
    ACMTechnicalCapabilityService,
)
