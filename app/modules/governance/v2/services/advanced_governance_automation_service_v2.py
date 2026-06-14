"""Governance v2 adapter for advanced governance automation service."""

import importlib

AdvancedGovernanceAutomationService = importlib.import_module(
    "app.services.advanced_governance_automation_service"
).AdvancedGovernanceAutomationService

__all__ = ["AdvancedGovernanceAutomationService"]
