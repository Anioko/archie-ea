"""DE-3 read path: the ONE accessor over the derived-fact store (ADR-004).

Every read applies ``stale = FALSE`` by default, in this one place, so
"forgot the filter" is not reachable from a caller. ``include_stale=True``
returns stale rows too, each carrying ``"stale": True`` and
``"reason": "derivation_stale"`` (the DE-14 closed-vocabulary member).

Task 03's endpoints are the only permitted callers beyond this module's own
tests -- no other read path over the store may exist at L1 (NFR-8).

Deliberately does NOT use ``app.jobs.tenant_safe_job.tenant_scope()`` (round-1
refuter finding D4). ``tenant_scope()`` is a background-job harness: it calls
``db.session.remove()`` on entry and exit, which is exactly right for a
scheduled job's own dedicated session lifecycle but destructive inside a live
request -- it discards the REQUEST's session (detaching whatever
``flask_login`` cached on ``g._login_user``, corrupting `after_request`
handlers that touch ``current_user``) and clobbers ``g.current_org`` for the
rest of the request (``tenant_scope``'s ``finally`` only restores
``current_org_id``). A request already has ``g.current_org_id`` set correctly
by the ordinary request lifecycle, and the existing tenant-isolation
``do_orm_execute`` listener (``app/middleware/tenant_isolation.py``) already
filters every ORM read by it -- no extra wrapper is needed or safe here. An
explicit ``organization_id`` equality check is still applied below as
defence-in-depth for the id-lookup path, matching the pattern used elsewhere
in this module for raw-SQL predicates.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.extensions import db
from app.modules.intelligence.services.reason_codes import validate_reason_code

STALE_REASON = validate_reason_code("derivation_stale")


def _apply_default_staleness_filter(stmt, model, include_stale: bool):
    """The one place the ``stale = FALSE`` default is applied (ADR-004).

    Isolated as its own function -- not inlined in ``list_derived_facts`` --
    so the task 02 mutation-proof test (acceptance item 13) can monkeypatch
    exactly this seam to simulate "the guard was removed" and confirm the
    stale-never-current test goes red, without editing source under test.
    """
    if include_stale:
        return stmt
    return stmt.where(model.stale.is_(False))


def _serialize(row) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": row.id,
        "organization_id": row.organization_id,
        "source_element_id": row.source_element_id,
        "target_element_id": row.target_element_id,
        "derived_type": row.derived_type,
        "rule_id": row.rule_id,
        "chain": list(row.chain or []),
        "chain_element_ids": list(row.chain_element_ids or []),
        "depth": row.depth,
        "confidence": float(row.confidence) if row.confidence is not None else None,
        "provenance": row.provenance,
        "engine_version": row.engine_version,
        "computed_at": row.computed_at.isoformat() if row.computed_at else None,
    }
    if row.stale:
        payload["stale"] = True
        payload["reason"] = STALE_REASON
    else:
        payload["stale"] = False
    return payload


def list_derived_facts(
    organization_id: int,
    *,
    include_stale: bool = False,
    source_element_id: Optional[int] = None,
    target_element_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """The single read path over ``archimate_derived_relationships``.

    Must be called inside ``app.app_context()``. Called from a request, the
    existing tenant-isolation ``do_orm_execute`` listener already filters
    this read by ``g.current_org_id``; the explicit ``organization_id ==``
    predicate below is defence-in-depth and is what makes this function
    correct even when called with no ambient request context (e.g. a future
    job caller), where the listener would otherwise no-op entirely.
    """
    from app.modules.intelligence.models.derived_relationship import DerivedRelationship

    stmt = db.select(DerivedRelationship).where(
        DerivedRelationship.organization_id == organization_id
    )
    stmt = _apply_default_staleness_filter(stmt, DerivedRelationship, include_stale)
    if source_element_id is not None:
        stmt = stmt.where(DerivedRelationship.source_element_id == source_element_id)
    if target_element_id is not None:
        stmt = stmt.where(DerivedRelationship.target_element_id == target_element_id)
    rows = db.session.execute(stmt).scalars().all()
    return [_serialize(r) for r in rows]


def get_derived_fact(
    organization_id: int, derived_id: int, *, include_stale: bool = True
) -> Optional[Dict[str, Any]]:
    """Fetch one derived fact by id, scoped to *organization_id*.

    ``include_stale`` defaults True here (unlike ``list_derived_facts``)
    because the provenance-expansion endpoint (API-2) is explicitly allowed
    to show a stale row's provenance -- it must still carry the flag; task 03
    is responsible for treating a cross-tenant id as a 404, which this
    function's tenant scoping already guarantees (a row outside
    *organization_id* is invisible, not merely denied).
    """
    from app.modules.intelligence.models.derived_relationship import DerivedRelationship

    stmt = db.select(DerivedRelationship).where(
        DerivedRelationship.id == derived_id,
        DerivedRelationship.organization_id == organization_id,
    )
    if not include_stale:
        stmt = stmt.where(DerivedRelationship.stale.is_(False))
    row = db.session.execute(stmt).scalar_one_or_none()
    return _serialize(row) if row is not None else None


__all__ = ["STALE_REASON", "get_derived_fact", "list_derived_facts"]
