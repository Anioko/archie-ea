"""
Automated wrapper generation for the compatibility layer.

Provides ``attach_compat_hooks()`` — the shared hook-attaching logic used by
all 13 per-module compat wrappers — and ``make_legacy_wrapper()`` which creates
the ``wrap_legacy_*_bp()`` functions.

Usage::

    from app.compat.deprecation_logger import CompatStats
    from app.compat.feature_flag_gate import make_compat_config
    from app.compat.wrapper_generator import make_legacy_wrapper

    _config = make_compat_config("vendors")

    class VendorsCompatStats(CompatStats):
        pass

    wrap_legacy_vendors_bp = make_legacy_wrapper(_config, VendorsCompatStats)
"""

import logging
import time
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request

from app.compat.feature_flag_gate import CompatConfig

# 90-day sunset window from migration start
_SUNSET_DATE = datetime(2026, 5, 15, tzinfo=timezone.utc)

logger = logging.getLogger(__name__)


def attach_compat_hooks(
    bp: Blueprint,
    config: CompatConfig,
    stats_cls: type,
) -> None:
    """Attach before_request / after_request hooks to a legacy blueprint.

    Handles AssertionError gracefully when blueprints have already been
    registered (e.g. during test app recreation with create_app()).

    Args:
        bp: The legacy Flask Blueprint to wrap.
        config: Module-specific compat configuration.
        stats_cls: CompatStats subclass to record hits on.
    """
    try:
        @bp.before_request
        def _compat_before():
            if not config.enabled:
                return None
            request._compat_start = time.monotonic()  # type: ignore[attr-defined]
            endpoint = request.endpoint or "unknown"
            logger.warning(
                "DEPRECATED legacy route hit: %s %s (endpoint=%s). Migrate to v2.",
                request.method,
                request.path,
                endpoint,
            )
            stats_cls.record(endpoint)
            return None

        @bp.after_request
        def _compat_after(response):
            if not config.enabled:
                return response
            response.headers["X-Deprecated"] = config.deprecation_msg
            response.headers["X-Migrate-To"] = config.v2_env_var
            # RFC 8594 standard deprecation headers
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = _SUNSET_DATE.strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            )
            start = getattr(request, "_compat_start", None)
            if start is not None:
                duration_ms = round((time.monotonic() - start) * 1000, 2)
                response.headers["X-Legacy-Response-Time-Ms"] = str(duration_ms)
            return response
    except AssertionError:
        logger.debug(
            "[COMPAT] Blueprint '%s' already registered, skipping hook attachment",
            bp.name,
        )


def make_legacy_wrapper(config: CompatConfig, stats_cls: type):
    """Create a wrap_legacy_*_bp function for a module.

    Returns a callable ``(Blueprint) -> Blueprint`` that attaches compat hooks
    and logs the wrapping.

    Args:
        config: Module-specific compat configuration.
        stats_cls: CompatStats subclass to record hits on.
    """
    def _wrap(bp: Blueprint) -> Blueprint:
        attach_compat_hooks(bp, config, stats_cls)
        logger.info(
            "[COMPAT] Legacy %s blueprint '%s' wrapped with deprecation hooks",
            config.module_name,
            bp.name,
        )
        return bp
    return _wrap
