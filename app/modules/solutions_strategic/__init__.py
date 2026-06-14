# mass-deletion-ok — v1→v2 migration: 94 lines of v1 register() replaced with v2 delegation stub
"""
Solutions & Strategic module — v1 routes DELETED.

All active routes and services are in app/modules/solutions_strategic/v2/.
This register() function is a fallback stub. Production uses v2 via
USE_SOLUTIONS_STRATEGIC_GUARDRAILS=true in app/_bootstrap/blueprints.py.
"""

import logging

from flask import Flask

from app.extensions import db  # noqa: F401 — re-exported for submodule imports

logger = logging.getLogger(__name__)


def register(app: Flask) -> None:
    """v1 registration stub — all v1 route files have been deleted.

    If this function is called, it means USE_SOLUTIONS_STRATEGIC_GUARDRAILS is
    false and USE_NEW_SOLUTIONS_STRATEGIC is true.  That configuration is not
    supported after the v1-to-v2 migration.  Log a clear error and delegate to v2.
    """
    app.logger.error(
        "[MODULE] solutions_strategic v1 register() called but v1 routes are "
        "deleted. Set USE_SOLUTIONS_STRATEGIC_GUARDRAILS=true to use v2. "
        "Falling through to v2 registration."
    )
    # Delegate to v2 so the app still boots
    from app.modules.solutions_strategic.v2 import register as _reg_v2

    _reg_v2(app)
