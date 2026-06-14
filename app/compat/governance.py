"""
Compatibility wrappers for the governance module (legacy -> v2).

Feature-flag gating: USE_GOVERNANCE_COMPAT=true (env) enables the wrappers.
"""

from app.compat.deprecation_logger import CompatStats
from app.compat.feature_flag_gate import make_compat_config
from app.compat.wrapper_generator import make_legacy_wrapper

_config = make_compat_config("governance")


class GovernanceCompatStats(CompatStats):
    """Thread-safe hit counter for legacy governance endpoints."""
    pass


wrap_legacy_governance_bp = make_legacy_wrapper(_config, GovernanceCompatStats)
