"""Governance v2 adapter for policy monitoring service."""

import importlib

PolicyMonitoringService = importlib.import_module(
    "app.services.policy_monitoring_service"
).PolicyMonitoringService

__all__ = ["PolicyMonitoringService"]
