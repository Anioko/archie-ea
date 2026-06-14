"""
Compatibility wrappers for the import_batch module (legacy -> v2).

Feature-flag gating: USE_IMPORT_BATCH_COMPAT=true (env) enables the wrappers.
"""

from app.compat.deprecation_logger import CompatStats
from app.compat.feature_flag_gate import make_compat_config
from app.compat.wrapper_generator import make_legacy_wrapper

_config = make_compat_config("import_batch")


class ImportBatchCompatStats(CompatStats):
    """Thread-safe hit counter for legacy import batch endpoints."""
    pass


wrap_legacy_import_batch_bp = make_legacy_wrapper(_config, ImportBatchCompatStats)
