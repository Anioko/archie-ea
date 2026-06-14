"""
Compatibility wrappers for the capabilities module (legacy -> v2).

Feature-flag gating: USE_CAPABILITIES_COMPAT=true (env) enables the wrappers.
"""

from app.compat.deprecation_logger import CompatStats
from app.compat.feature_flag_gate import make_compat_config
from app.compat.wrapper_generator import make_legacy_wrapper

_config = make_compat_config("capabilities")


class CapabilitiesCompatStats(CompatStats):
    """Thread-safe hit counter for legacy capability endpoints."""
    pass


wrap_legacy_capabilities_bp = make_legacy_wrapper(_config, CapabilitiesCompatStats)
