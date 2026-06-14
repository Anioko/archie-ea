"""
Compatibility wrappers for the duplicate_detection module (legacy -> v2).

Feature-flag gating: USE_DEDUPE_COMPAT=true (env) enables the wrappers.
"""

from app.compat.deprecation_logger import CompatStats
from app.compat.feature_flag_gate import make_compat_config
from app.compat.wrapper_generator import make_legacy_wrapper

_config = make_compat_config("duplicate_detection", compat_key="DEDUPE")


class DedupeCompatStats(CompatStats):
    """Thread-safe hit counter for legacy dedupe endpoints."""
    pass


wrap_legacy_dedupe_bp = make_legacy_wrapper(_config, DedupeCompatStats)
