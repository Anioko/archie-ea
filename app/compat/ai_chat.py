"""
Compatibility wrappers for the ai_chat module (legacy -> v2).

Feature-flag gating: USE_AI_CHAT_COMPAT=true (env) enables the wrappers.
"""

from app.compat.deprecation_logger import CompatStats
from app.compat.feature_flag_gate import make_compat_config
from app.compat.wrapper_generator import make_legacy_wrapper

_config = make_compat_config("ai_chat")


class AIChatCompatStats(CompatStats):
    """Thread-safe hit counter for legacy AI chat endpoints."""
    pass


wrap_legacy_ai_chat_bp = make_legacy_wrapper(_config, AIChatCompatStats)
