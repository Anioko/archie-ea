"""
Feature flag gating for the compatibility layer.

Provides ``CompatConfig`` — a configuration container for per-module compat
settings including environment variable names and deprecation messages.

Usage::

    from app.compat.feature_flag_gate import make_compat_config

    _config = make_compat_config("monitoring")
    # _config.enabled       -> True/False (reads USE_MONITORING_COMPAT env dynamically)
    # _config.v2_env_var    -> "USE_MONITORING_GUARDRAILS"
    # _config.deprecation_msg -> "DEPRECATED: ... Set USE_MONITORING_GUARDRAILS=true ..."

For modules with non-standard env var names (e.g. duplicate_detection uses
DEDUPE), pass ``compat_key``::

    _config = make_compat_config("duplicate_detection", compat_key="DEDUPE")
"""

import os


class CompatConfig:
    """Configuration for a compatibility module.

    The ``enabled`` property reads the environment variable on each access,
    so that module reloads and runtime env changes take effect immediately.
    """

    __slots__ = ("module_name", "compat_env_var", "v2_env_var", "deprecation_msg")

    def __init__(self, module_name: str, compat_env_var: str, v2_env_var: str,
                 deprecation_msg: str):
        self.module_name = module_name
        self.compat_env_var = compat_env_var
        self.v2_env_var = v2_env_var
        self.deprecation_msg = deprecation_msg

    @property
    def enabled(self) -> bool:
        """Check if compat wrappers are enabled (reads env var dynamically)."""
        return os.environ.get(self.compat_env_var, "true").lower() != "false"


def make_compat_config(module_name: str, compat_key: str = None) -> CompatConfig:
    """Create compat configuration for a module.

    Args:
        module_name: Human-readable module name (e.g. "monitoring").
        compat_key: Override for env var key (e.g. "DEDUPE" instead of
                    "DUPLICATE_DETECTION"). Defaults to module_name.upper().

    Returns:
        CompatConfig with all settings resolved.
    """
    key = (compat_key or module_name).upper()
    compat_env_var = f"USE_{key}_COMPAT"
    v2_env_var = f"USE_{key}_V2"
    deprecation_msg = (
        "DEPRECATED: This endpoint is served by legacy code. "
        f"Set {v2_env_var}=true to use the guardrail-enabled v2 module."
    )
    return CompatConfig(
        module_name=module_name,
        compat_env_var=compat_env_var,
        v2_env_var=v2_env_var,
        deprecation_msg=deprecation_msg,
    )
