"""
DEPRECATED: Import from app.modules.capabilities.services instead.
-> app.modules.capabilities.services.analysis_service

Backward-compat re-export. Canonical: app/modules/capabilities/services/capability_discovery_agent.py
"""

from app.modules.capabilities.services.capability_discovery_agent import (  # noqa: F401
    CapabilityClassification,
    CapabilityDiscoveryAgent,
    DiscoveredCapability,
)
