"""Intelligence module (Four Intelligences extension) — DE-1..DE-18, sdd-v2.md AA-1.

``register(app)`` is the one place later tasks attach their pieces: the API
blueprint and the ORM invalidation hook (T-003), the UI blueprint (T-004).

T-001 mounts nothing. Derivation Runner (DE-1) computes and returns a
``DerivationResult`` but writes nothing, so there is no route, template or
table for this module to register yet — sdd-v2.md OA-5: L0 ships before any
query surface.
"""

from __future__ import annotations


def register(app) -> None:
    """Register the intelligence module's blueprints and event hooks.

    T-003 adds the ORM invalidation hook (DE-3) and the API blueprint
    (DE-4, the recompute + provenance-expansion routes); T-004 adds the UI
    blueprint. Both non-fatal: a failure here degrades this one feature, not
    the whole app (CLAUDE.md "Blueprints register non-fatally").
    """
    try:
        from app.modules.intelligence.services.invalidation import (
            register_invalidation_listener,
        )

        register_invalidation_listener()
    except Exception:
        app.logger.exception(
            "[MODULE] intelligence: invalidation listener registration failed"
        )

    try:
        from app.modules.intelligence.routes.api import intelligence_api

        app.register_blueprint(intelligence_api)
    except Exception:
        app.logger.exception(
            "[MODULE] intelligence: API blueprint registration failed"
        )


__all__ = ["register"]
