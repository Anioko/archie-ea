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

    Nothing is mounted yet. T-003 adds the API blueprint and the ORM
    invalidation hook; T-004 adds the UI blueprint — both at this one place,
    so a later task extends this function rather than inventing a second
    registration point for the module.
    """
    return None


__all__ = ["register"]
