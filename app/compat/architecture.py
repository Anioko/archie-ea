"""
Compatibility wrappers for the architecture module (legacy -> v2).

Feature-flag gating: USE_ARCHITECTURE_COMPAT=true (env) enables the wrappers.
"""

from app.compat.deprecation_logger import CompatStats
from app.compat.feature_flag_gate import make_compat_config
from app.compat.wrapper_generator import make_legacy_wrapper

_config = make_compat_config("architecture")


class ArchitectureCompatStats(CompatStats):
    """Thread-safe hit counter for legacy architecture endpoints."""
    pass


wrap_legacy_architecture_bp = make_legacy_wrapper(_config, ArchitectureCompatStats)
