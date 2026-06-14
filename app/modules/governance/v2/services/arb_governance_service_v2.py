"""Governance v2 adapter for ARB governance service."""

import importlib

ARBGovernanceService = importlib.import_module("app.services.arb_governance_service").ARBGovernanceService

__all__ = ["ARBGovernanceService"]
