"""DE-1: the Derivation Runner (FR-1) — the derivation engine's only caller.

Loads a tenant's ArchiMate model, calls the ADR-002-v2-extended
``compute_derived``, and returns a ``DerivationResult``. Computes only: it
does not persist anything, expose a route, or render a screen. The
derived-fact table, its upsert, the invalidation hook and the recompute job
belong to T-003 (sdd-v2.md AA-3; ADR-003 — derivation never runs in the
write path).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.extensions import db
from app.jobs.tenant_safe_job import tenant_scope
from app.services.archimate_derivation_service import ArchiMateDerivationService

# The module constant AA-3 requires: a later rule change bumps this, which is
# what makes T-003's recompute selectively re-triggerable rather than a
# blanket recompute of every tenant regardless of whether its rules changed.
ENGINE_VERSION = "1.0.0"


@dataclass(frozen=True)
class DerivationResult:
    """The outcome of one ``DerivationRunner.run()`` call, for one tenant.

    ``ratio`` is ``None`` rather than ``0`` when ``explicit_count`` is zero —
    a measured zero and "not computed" must stay distinguishable (CLAUDE.md
    "Never invent data": a 0 that means "not computed" is indistinguishable
    from a measured zero).

    ``derived`` carries the raw rows ``compute_derived`` returned (each with
    ``source_id``, ``target_id``, ``type``, ``chain``, ``depth``,
    ``relationship_chain``, ``rule_id`` — ADR-002-v2). Nothing here persists
    them; T-003's upsert is the first consumer.
    """

    explicit_count: int
    derived_count: int
    ratio: Optional[float]
    duration_ms: int
    engine_version: str
    derived: List[Dict[str, Any]] = field(default_factory=list)


class DerivationRunner:
    """DE-1. The only caller of ``ArchiMateDerivationService.compute_derived``."""

    def __init__(self, service: Optional[ArchiMateDerivationService] = None) -> None:
        self._service = service or ArchiMateDerivationService()

    def run(self, organization_id: int) -> DerivationResult:
        """Compute derived relationships for one tenant.

        Must run inside an ``app.app_context()`` — ``tenant_scope`` requires
        one. Tenant scope comes from ``tenant_scope()`` only: the ORM reads
        below carry no hand-written ``organization_id`` predicate, so the
        existing ``do_orm_execute`` listener does the filtering and this
        runner cannot double-filter (AA-3; CLAUDE.md "Multi-tenancy is
        implicit").
        """
        # Deferred import: avoids importing the whole app.models package at
        # module-import time, matching the lazy-model-import convention used
        # elsewhere in this codebase (e.g. app/commands/archimate_commands.py).
        from app.models import ArchiMateElement, ArchiMateRelationship

        started = time.monotonic()

        with tenant_scope(organization_id):
            element_rows = db.session.execute(db.select(ArchiMateElement)).scalars().all()
            relationship_rows = (
                db.session.execute(db.select(ArchiMateRelationship)).scalars().all()
            )

            elements = [
                {"id": e.id, "name": e.name, "type": e.type, "layer": e.layer}
                for e in element_rows
            ]
            relationships = [
                {
                    "id": r.id,
                    "source_id": r.source_id,
                    "target_id": r.target_id,
                    "type": r.type,
                }
                for r in relationship_rows
            ]

            derived = self._service.compute_derived(elements, relationships)

        duration_ms = int((time.monotonic() - started) * 1000)
        explicit_count = len(relationships)
        derived_count = len(derived)
        ratio = (derived_count / explicit_count) if explicit_count else None

        return DerivationResult(
            explicit_count=explicit_count,
            derived_count=derived_count,
            ratio=ratio,
            duration_ms=duration_ms,
            engine_version=ENGINE_VERSION,
            derived=derived,
        )


__all__ = ["DerivationRunner", "DerivationResult", "ENGINE_VERSION"]
