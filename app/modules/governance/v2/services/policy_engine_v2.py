"""Governance v2 adapter for policy engine service."""

import importlib

_policy_engine_module = importlib.import_module("app.services.policy_engine")
PolicyEngine = _policy_engine_module.PolicyEngine
PolicyEvaluation = _policy_engine_module.PolicyEvaluation
PolicyResult = _policy_engine_module.PolicyResult
PolicyRule = _policy_engine_module.PolicyRule
PolicyScope = _policy_engine_module.PolicyScope

__all__ = [
    "PolicyEngine",
    "PolicyEvaluation",
    "PolicyResult",
    "PolicyRule",
    "PolicyScope",
]
