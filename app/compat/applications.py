"""
Compatibility wrappers for the applications module (legacy -> v2).

Feature-flag gating: USE_APPLICATIONS_COMPAT=true (env) enables the wrappers.
"""

from app.compat.deprecation_logger import CompatStats
from app.compat.feature_flag_gate import make_compat_config
from app.compat.wrapper_generator import make_legacy_wrapper

_config = make_compat_config("applications")


class ApplicationsCompatStats(CompatStats):
    """Thread-safe hit counter for legacy applications endpoints."""
    pass


wrap_legacy_applications_bp = make_legacy_wrapper(_config, ApplicationsCompatStats)
