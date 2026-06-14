"""
DEPRECATED: Import from app.modules.capabilities.services instead.
-> app.modules.capabilities.services.analysis_service

Backward-compat re-export. Canonical: app/modules/capabilities/services/capability_heatmap_service.py
"""

from app.modules.capabilities.services.capability_heatmap_service import (  # noqa: F401
    CapabilityHeatmapService,
    QueryCounter,
)
