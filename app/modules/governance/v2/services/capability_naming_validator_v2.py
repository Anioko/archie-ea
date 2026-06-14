"""Governance v2 alias for capability naming validator."""

from app.modules.capabilities.services.capability_naming_validator import (
    CapabilityNamingValidator,
    NamingIssue,
)

__all__ = ["CapabilityNamingValidator", "NamingIssue"]
