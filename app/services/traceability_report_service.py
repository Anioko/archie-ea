"""ARCH-126: measure model traceability gaps (elements with zero relationships,
solutions with zero capability links).

This is deliberately a *measurement*, not a fix — the underlying gap (61% of
ArchiMate elements unconnected, solutions linking to 0 capabilities) is a data
population problem the register explicitly says must not be papered over with
fabricated links. What engineering can do is make the gap visible and
re-measurable rather than a one-off manual count in a report.

Tenant scoping: every query here runs through the plain ORM `Model.query` on
TenantMixin-derived tables, so inside a request context (`g.current_org_id`
set) the ORM event in ``app/middleware/tenant_isolation.py`` injects the
``organization_id`` filter automatically — no hand-written predicate is added
here, per the project convention. Outside a request context (this module's
CLI command included) there is no ``g.current_org_id`` and results are
therefore computed across all organizations; the CLI command documents that.
"""

from __future__ import annotations

from typing import TypedDict

from app import db


class TraceabilityReport(TypedDict):
    elements_total: int
    elements_with_zero_relationships: int
    elements_with_zero_relationships_pct: float | None
    solutions_total: int
    solutions_with_zero_capability_links: int
    solutions_with_zero_capability_links_pct: float | None


def _pct(numerator: int, denominator: int) -> float | None:
    """Real computed zero is a real number; only an empty denominator is
    uncomputable and must render as None -> em dash, never a fabricated 0."""
    if denominator == 0:
        return None
    return round(100.0 * numerator / denominator, 1)


def compute_traceability_report() -> TraceabilityReport:
    """Compute the two ARCH-126 measurements against the current tenant scope.

    Returns real integers (including real zeros) for every count. The
    denominators can legitimately be 0 on an empty tenant, in which case the
    corresponding percentage is None (uncomputable), not 0.
    """
    from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
    from app.models.solution_models import Solution, SolutionCapabilityMapping

    elements_total = ArchiMateElement.query.count()

    # Element ids referenced by at least one relationship, source or target.
    src_ids = db.session.query(ArchiMateRelationship.source_id).filter(
        ArchiMateRelationship.source_id.isnot(None)
    )
    tgt_ids = db.session.query(ArchiMateRelationship.target_id).filter(
        ArchiMateRelationship.target_id.isnot(None)
    )
    connected_ids = {row[0] for row in src_ids.all()} | {row[0] for row in tgt_ids.all()}

    if elements_total:
        elements_with_zero_relationships = (
            ArchiMateElement.query.filter(~ArchiMateElement.id.in_(connected_ids)).count()
            if connected_ids
            else elements_total
        )
    else:
        elements_with_zero_relationships = 0

    solutions_total = Solution.query.count()
    linked_solution_ids = {
        row[0]
        for row in db.session.query(SolutionCapabilityMapping.solution_id)
        .filter(SolutionCapabilityMapping.solution_id.isnot(None))
        .distinct()
        .all()
    }
    if solutions_total:
        solutions_with_zero_capability_links = (
            Solution.query.filter(~Solution.id.in_(linked_solution_ids)).count()
            if linked_solution_ids
            else solutions_total
        )
    else:
        solutions_with_zero_capability_links = 0

    return {
        "elements_total": elements_total,
        "elements_with_zero_relationships": elements_with_zero_relationships,
        "elements_with_zero_relationships_pct": _pct(
            elements_with_zero_relationships, elements_total
        ),
        "solutions_total": solutions_total,
        "solutions_with_zero_capability_links": solutions_with_zero_capability_links,
        "solutions_with_zero_capability_links_pct": _pct(
            solutions_with_zero_capability_links, solutions_total
        ),
    }
