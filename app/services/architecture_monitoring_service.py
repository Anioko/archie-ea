# DEPRECATED: Import from app.modules.architecture.services.architecture_monitoring_service instead.
"""Backward-compatibility shim. Canonical: app/modules/architecture/services/architecture_monitoring_service.py"""
from app.modules.architecture.services.architecture_monitoring_service import (  # noqa: F401,F403
    AlertType,
    AlertSeverity,
    MonitoringStatus,
    ArchitectureAlert,
    ArchitectureBaseline,
    DriftAnalysis,
    ArchitectureMonitoringService,
)
