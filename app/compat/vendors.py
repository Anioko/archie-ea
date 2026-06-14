"""
Compatibility wrappers for the vendors module (legacy -> v2).

Feature-flag gating: USE_VENDORS_COMPAT=true (env) enables the wrappers.
"""

from app.compat.deprecation_logger import CompatStats
from app.compat.feature_flag_gate import make_compat_config
from app.compat.wrapper_generator import make_legacy_wrapper

_config = make_compat_config("vendors")


class VendorsCompatStats(CompatStats):
    """Thread-safe hit counter for legacy vendor endpoints."""
    pass


wrap_legacy_vendors_bp = make_legacy_wrapper(_config, VendorsCompatStats)
