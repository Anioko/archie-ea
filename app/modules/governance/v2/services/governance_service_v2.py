"""Governance v2 adapter for governance service."""

import importlib

GovernanceService = importlib.import_module("app.services.governance_service").GovernanceService

__all__ = ["GovernanceService"]
