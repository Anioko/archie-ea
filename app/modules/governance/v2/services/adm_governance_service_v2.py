"""Governance v2 adapter for ADM governance service."""

import importlib

_adm_governance_module = importlib.import_module("app.services.adm_governance_service")
ADMGovernanceService = _adm_governance_module.ADMGovernanceService
adm_governance_service = _adm_governance_module.adm_governance_service

__all__ = ["ADMGovernanceService", "adm_governance_service"]
