"""
Compatibility wrappers for the solutions_strategic module (legacy -> v2).

Feature-flag gating: USE_SOLUTIONS_STRATEGIC_COMPAT=true (env) enables the wrappers.
"""

from app.compat.deprecation_logger import CompatStats
from app.compat.feature_flag_gate import make_compat_config
from app.compat.wrapper_generator import make_legacy_wrapper

_config = make_compat_config("solutions_strategic")


class SolutionsStrategicCompatStats(CompatStats):
    """Thread-safe hit counter for legacy solutions_strategic endpoints."""
    pass


wrap_legacy_solutions_strategic_bp = make_legacy_wrapper(_config, SolutionsStrategicCompatStats)
