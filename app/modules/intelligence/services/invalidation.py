"""Batched invalidation of derived facts.

An ``after_flush`` SQLAlchemy session-event listener that marks affected
``archimate_derived_relationships`` rows stale in **one** batched ``UPDATE``
per (flush, tenant) pair, inside the user's own flush so staleness commits or
rolls back with the model write it responds to. Never asynchronous,
never a second statement per id.

A second, ``do_orm_execute`` listener covers ORM-enabled bulk ``UPDATE``/
``DELETE`` (e.g. ``Model.query.delete()``), which never populates
``session.new``/``dirty``/``deleted`` and so is invisible to the after_flush
listener above.

Registered once by ``app/modules/intelligence/__init__.py::register(app)`` —
not at model-import time, so it can be skipped cleanly if the module fails to
import (non-fatal blueprint registration, CLAUDE.md).
"""

from __future__ import annotations

import datetime as _dt
import logging
import threading
from typing import Optional

from app.extensions import db

logger = logging.getLogger(__name__)

# stale_reason values are NOT members of the closed vocabulary of
# user-facing absence reasons in reason_codes.py ("derivation_stale" is the
# one member relevant here, applied by the read accessor in
# derived_facts.py, not written here). These are the internal cause codes
# the invalidation listener stamps on the row itself.
_REASON_RELATIONSHIP_CREATED = "relationship_created"
_REASON_RELATIONSHIP_UPDATED = "relationship_updated"
_REASON_RELATIONSHIP_DELETED = "relationship_deleted"
_REASON_ELEMENT_DELETED = "element_deleted"
_REASON_BULK_OPERATION = "bulk_operation"

# Guard against the listener's own UPDATE re-triggering itself: after_flush
# fires again for any flush its own statement causes SQLAlchemy to emit, and
# the raw UPDATE below touches no ORM-mapped objects, so there is nothing in
# session.new/dirty/deleted for a recursive call to find. This flag is a
# belt-and-suspenders re-entrancy guard for the (untested-in-practice) case
# of a nested flush triggered by something else during the UPDATE itself.
#
# THREAD-LOCAL, not a module global: gunicorn is
# configured with worker_class="gthread", threads=4 (gunicorn.conf.py), so a
# single worker process runs several requests' Python code concurrently on
# different OS threads sharing this module's globals. A module-level bool
# would let thread A's in-flight marking (between setting the flag and the DB
# round-trip completing) cause thread B's completely unrelated flush, for a
# different organization, to see the flag set and return 0 with no error and
# no log -- silently leaving that org's derived rows stale=false forever,
# with no path to self-heal since the recompute job only selects orgs that
# already carry a stale row. threading.local() gives each OS thread (and
# therefore each concurrently-handled request) its own flag.
_state = threading.local()


def _is_marking() -> bool:
    return getattr(_state, "marking_in_progress", False)


def _set_marking(value: bool) -> None:
    _state.marking_in_progress = value


def _collect_changes_by_org(session):
    """Inspect session.new/dirty/deleted for the two watched model types.

    Returns ``{organization_id: {stale_reason: {"relationship_ids": set(),
    "element_ids": set()}}}`` or ``{}`` when nothing watched changed in this
    flush. Grouped by organization_id: a single
    flush is not guaranteed to be single-tenant -- CLAUDE.md documents
    importers/CLI commands/anything looping over tenants inside one session
    as a real, existing pattern in this repo, and a flush spanning two
    tenants must mark both, not just whichever object happened to be first in
    session.new.
    """
    from app.models import ArchiMateElement, ArchiMateRelationship

    changes: dict[int, dict[str, dict[str, set]]] = {}

    def _add(org_id, reason: str, *, relationship_id=None, element_id=None):
        if org_id is None:
            # Nothing tenant-stamped yet on this object -- nothing safe to
            # scope an UPDATE to for it specifically; other objects in the
            # same flush that DO carry an organization_id are still handled.
            return
        org_bucket = changes.setdefault(org_id, {})
        bucket = org_bucket.setdefault(reason, {"relationship_ids": set(), "element_ids": set()})
        if relationship_id is not None:
            bucket["relationship_ids"].add(relationship_id)
        if element_id is not None:
            bucket["element_ids"].add(element_id)

    for obj in session.new:
        if isinstance(obj, ArchiMateRelationship) and obj.id is not None:
            _add(
                getattr(obj, "organization_id", None),
                _REASON_RELATIONSHIP_CREATED,
                relationship_id=obj.id,
            )

    for obj in session.dirty:
        if isinstance(obj, ArchiMateRelationship) and obj.id is not None:
            _add(
                getattr(obj, "organization_id", None),
                _REASON_RELATIONSHIP_UPDATED,
                relationship_id=obj.id,
            )

    for obj in session.deleted:
        if isinstance(obj, ArchiMateRelationship) and obj.id is not None:
            _add(
                getattr(obj, "organization_id", None),
                _REASON_RELATIONSHIP_DELETED,
                relationship_id=obj.id,
            )
        elif isinstance(obj, ArchiMateElement) and obj.id is not None:
            _add(
                getattr(obj, "organization_id", None),
                _REASON_ELEMENT_DELETED,
                element_id=obj.id,
            )

    return changes


def _mark_stale_for_org(session, organization_id: int, changes: dict) -> Optional[int]:
    """Issue the single batched UPDATE for one organization's changes in this flush.

    Returns the number of rows marked, or ``None`` when the database driver
    reported an unknown (negative) rowcount -- distinguished from an actual
    zero: "unknown" and "marked none" are not the same fact and must not be
    coerced together in the invalidation record.
    """
    all_relationship_ids: set[int] = set()
    all_element_ids: set[int] = set()
    for bucket in changes.values():
        all_relationship_ids |= bucket["relationship_ids"]
        all_element_ids |= bucket["element_ids"]

    case_parts = []
    params: dict = {
        "organization_id": organization_id,
        "now": _dt.datetime.utcnow(),
    }
    relationship_ids_all = sorted(all_relationship_ids) or None
    element_ids_all = sorted(all_element_ids) or None
    params["changed_relationship_ids"] = relationship_ids_all or []
    params["changed_element_ids"] = element_ids_all or []

    for idx, (reason, bucket) in enumerate(changes.items()):
        rel_ids = sorted(bucket["relationship_ids"])
        elem_ids = sorted(bucket["element_ids"])
        conditions = []
        if rel_ids:
            params[f"rel_reason_{idx}"] = rel_ids
            conditions.append(f"chain && CAST(:rel_reason_{idx} AS integer[])")
        if elem_ids:
            params[f"elem_reason_{idx}"] = elem_ids
            conditions.append(f"source_element_id = ANY(CAST(:elem_reason_{idx} AS integer[]))")
            conditions.append(f"target_element_id = ANY(CAST(:elem_reason_{idx} AS integer[]))")
        if not conditions:
            continue
        params[f"reason_{idx}"] = reason
        case_parts.append(f"WHEN {' OR '.join(conditions)} THEN :reason_{idx}")

    if not case_parts:
        return 0

    case_sql = "CASE " + " ".join(case_parts) + " ELSE stale_reason END"

    where_conditions = [
        "chain && CAST(:changed_relationship_ids AS integer[])",
        "source_element_id = ANY(CAST(:changed_element_ids AS integer[]))",
        "target_element_id = ANY(CAST(:changed_element_ids AS integer[]))",
    ]

    sql = f"""
        UPDATE archimate_derived_relationships
        SET stale = TRUE,
            stale_since = :now,
            stale_reason = {case_sql}
        WHERE organization_id = :organization_id
          AND stale = FALSE
          AND ({' OR '.join(where_conditions)})
    """

    result = session.execute(db.text(sql), params)
    if result.rowcount is None or result.rowcount < 0:
        return None
    return result.rowcount


def mark_stale_for_flush(session) -> int:
    """Issue one batched UPDATE per organization touched by this flush.

    Returns the total number of rows marked across all organizations in this
    flush (0 when nothing watched changed). ``None`` per-org counts (unknown
    rowcount) are recorded individually via ``record_invalidation`` but
    contribute 0 to this aggregate return value -- callers of this function
    for a return value want a count, not an unknown; the invalidation record
    is the place "unknown" is preserved. Safe to call directly from a test that
    wants a return value without going through the event system.
    """
    if _is_marking():
        return 0

    changes_by_org = _collect_changes_by_org(session)
    if not changes_by_org:
        return 0

    from app.modules.intelligence.services.observability import record_invalidation

    total_marked = 0
    _set_marking(True)
    try:
        for organization_id, changes in changes_by_org.items():
            marked = _mark_stale_for_org(session, organization_id, changes)
            if marked:
                record_invalidation(organization_id=organization_id, invalidated_rows=marked)
                total_marked += marked
            elif marked is None:
                record_invalidation(organization_id=organization_id, invalidated_rows=None)
    finally:
        _set_marking(False)

    return total_marked


def _mark_stale_bulk(
    session, organization_id: Optional[int], *, allow_global: bool = False
) -> Optional[int]:
    """Conservative fallback for a bulk ORM UPDATE/DELETE.

    A bulk statement (``Model.query.delete()``/``.update()``) carries no
    per-row ids the way ``session.new``/``dirty``/``deleted`` does, and its
    WHERE clause is not reliably introspectable here. Rather than risk
    leaving affected derived rows silently ``stale=false``, mark the entire
    derived-fact store stale for the affected scope:

      * ``organization_id`` set (a bulk write inside a tenant-scoped request
        or job) -- mark that tenant's store only.
      * ``organization_id`` is ``None`` *and* ``allow_global`` is ``True`` --
        an explicitly-global caller (``mark_all_stale(None)``, the
        ``flask archimate clear`` CLI entry point) -- mark every tenant's
        store, since the write itself was genuinely global.
      * ``organization_id`` is ``None`` and ``allow_global`` is ``False`` --
        an in-request/mapper-event bulk write with no resolvable tenant
        context. Broadcasting a global
        ``stale = TRUE`` here would blank every OTHER tenant's derived-fact
        store off the back of one tenant's ordinary write, which is a worse
        outcome than leaving a bulk write's rows unflagged. Skip cleanly
        instead: some rows are
        left stale-but-not-flagged, which the scheduled ``mark_all_stale``
        sweep / recompute job is the designed backstop for, not this
        listener silently corrupting every other tenant's read surface.
    """
    if organization_id is None and not allow_global:
        logger.warning(
            "invalidation: bulk ORM write with no resolvable organization_id "
            "and allow_global=False -- skipping stale-mark rather than "
            "broadcasting a global UPDATE"
        )
        return None

    now = _dt.datetime.utcnow()
    params: dict = {"now": now, "reason": _REASON_BULK_OPERATION}
    where = "stale = FALSE"
    if organization_id is not None:
        where += " AND organization_id = :organization_id"
        params["organization_id"] = organization_id

    sql = f"""
        UPDATE archimate_derived_relationships
        SET stale = TRUE,
            stale_since = :now,
            stale_reason = :reason
        WHERE {where}
    """
    result = session.execute(db.text(sql), params)
    if result.rowcount is None or result.rowcount < 0:
        return None
    return result.rowcount


def mark_all_stale(organization_id: Optional[int] = None) -> Optional[int]:
    """Public, explicit invalidation entry point for callers outside the ORM
    event system (e.g. a CLI command that bulk-deletes ArchiMate data
    directly).

    The ``do_orm_execute`` bulk listener already catches ``Model.query.
    delete()``/``.update()`` generically, but a specific known bulk-delete
    site (``flask archimate clear``, ``app/commands/archimate_commands.py``)
    calls this explicitly too, as belt-and-suspenders: a change in how that
    command issues its deletes (e.g. moving to raw SQL, which no ORM event
    can see at all) must not silently reintroduce the same staleness gap.

    ``organization_id=None`` marks every tenant's store stale -- the correct
    scope for a command that itself deletes across every tenant.
    """
    session = db.session
    if _is_marking():
        # Reentrant call while a marking is already in flight on this
        # thread. This is "unknown whether anything was marked", not "marked
        # zero rows": a bare 0 here is indistinguishable from a genuine
        # no-op run, and the invalidation record must not conflate the two.
        return None
    _set_marking(True)
    try:
        marked = _mark_stale_bulk(session, organization_id, allow_global=True)
    finally:
        _set_marking(False)

    from app.modules.intelligence.services.observability import record_invalidation

    record_invalidation(organization_id=organization_id, invalidated_rows=marked)
    return marked


def _after_flush_listener(session, flush_context):
    try:
        mark_stale_for_flush(session)
    except Exception:
        # A failed marking must surface as an error, never as a silently
        # unmarked store (error-signalling / silent-data gates) -- but it
        # must also not corrupt the flush that triggered it. Re-raising here
        # rolls back the whole transaction (model write + staleness marking
        # together), which is the correct outcome per ADR-004: if staleness
        # cannot be recorded, the model write must not silently "win".
        logger.exception("invalidation: marking failed for this flush")
        raise


def _do_orm_execute_bulk_listener(orm_execute_state):
    """Catch ORM-enabled bulk UPDATE/DELETE on the two watched models.

    ``Model.query.delete()`` / ``Model.query.update()`` (and the 2.0-style
    ``session.execute(delete(Model))``/``update(Model)``) never populate
    ``session.new``/``dirty``/``deleted`` -- SQLAlchemy sends the statement
    straight to the database without materialising the affected rows as
    Python objects -- so ``_after_flush_listener`` above is structurally
    blind to them. This listener is the only thing that sees a bulk write.

    Ordinary per-instance ``session.delete(obj)`` / attribute-dirty updates
    are NOT bulk-enabled statements and do not reach this listener at all
    (they are handled entirely by the flush's own INSERT/UPDATE/DELETE
    emission, which does not pass through ``do_orm_execute``) -- so there is
    no double-marking between this listener and the after_flush one.
    """
    if not (orm_execute_state.is_update or orm_execute_state.is_delete):
        return
    if _is_marking():
        return

    try:
        from app.models import ArchiMateElement, ArchiMateRelationship
    except Exception:  # pragma: no cover - defensive, models package missing
        return

    watched = (ArchiMateElement, ArchiMateRelationship)
    try:
        entity = orm_execute_state.bind_mapper.class_
    except Exception:
        entity = None
    if entity not in watched:
        return

    from flask import g

    organization_id = getattr(g, "current_org_id", None) if _has_app_context() else None

    session = orm_execute_state.session
    _set_marking(True)
    try:
        marked = _mark_stale_bulk(session, organization_id)
    finally:
        _set_marking(False)

    from app.modules.intelligence.services.observability import record_invalidation

    # organization_id may legitimately be None here (an estate-wide bulk
    # write) -- record_invalidation's own contract is "whatever scope this
    # marking applied to", and None-scope is itself information, not a bug.
    record_invalidation(organization_id=organization_id, invalidated_rows=marked)


def _has_app_context() -> bool:
    from flask import has_app_context

    return has_app_context()


def register_invalidation_listener() -> None:
    """Attach the invalidation listeners to the scoped session, once.

    Idempotent: SQLAlchemy's ``event.listen`` would otherwise stack a second
    listener on a second call (e.g. two ``create_app()`` calls in one
    process, which ``tests/test_boot_health.py`` documents happening).
    """
    if not db.event.contains(db.session, "after_flush", _after_flush_listener):
        db.event.listen(db.session, "after_flush", _after_flush_listener)
    if not db.event.contains(db.session, "do_orm_execute", _do_orm_execute_bulk_listener):
        db.event.listen(db.session, "do_orm_execute", _do_orm_execute_bulk_listener)


__all__ = [
    "mark_all_stale",
    "mark_stale_for_flush",
    "register_invalidation_listener",
]
