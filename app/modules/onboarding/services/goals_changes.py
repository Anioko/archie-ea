"""Goals and changes captured at onboarding, written to the real tables.

*Goal* -- what the founder wants to achieve. It is an ArchiMate Goal element for
the organisation and nothing else. The ``goals`` and ``drivers`` tables carry no
``organization_id``, so a row written there by one tenant is readable by every
other; the tenant-scoped element is the only safe home until those tables are
tenant-scoped. ``custom_properties`` carries the optional date and measure.

*Change* -- something planned or under way. It is a ``WorkPackage`` for the
organisation, mirrored into the ArchiMate model through the backbone helper, and
linked to the goal it serves by a Realization relationship when the ArchiMate
rules allow one.

Onboarding never deletes either. Names already present (from anywhere else in the
product) are reused and their existing values are only filled in, never
overwritten with blanks.
"""
from __future__ import annotations

import datetime

from app import db
from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
from app.models.implementation_migration import WorkPackage
from app.modules.architecture.services.archimate_relationship_service import ArchiMateRelationshipService
from app.services.archimate_backbone import create_backbone_element, sync_archimate_element

STATUSES = (
    {"key": "planned", "label": "Planned"},
    {"key": "in_progress", "label": "Under way"},
    {"key": "completed", "label": "Done"},
)
_STATUS_KEYS = {s["key"] for s in STATUSES}
_MAX_NAME = 100  # ArchiMateElement.name is String(100)
_MAX_MEASURE = 200


def _clean(value, limit) -> str | None:
    text = (str(value) if value is not None else "").strip()
    return text[:limit] or None


def _date(value) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(str(value).strip()[:10])
    except (TypeError, ValueError):
        return None


def _goal_elements() -> dict[str, ArchiMateElement]:
    rows = ArchiMateElement.query.filter_by(type="Goal", layer="Motivation").all()
    return {(r.name or "").strip().lower(): r for r in rows}


def read() -> dict:
    goals = [
        {
            "id": g.id,
            "name": g.name,
            "by_when": (g.custom_properties or {}).get("target_date") or "",
            "measure": (g.custom_properties or {}).get("measure") or "",
        }
        for g in sorted(_goal_elements().values(), key=lambda e: e.id)
    ]
    goal_by_id = {g["id"]: g["name"] for g in goals}
    serves = {
        r.source_id: goal_by_id.get(r.target_id)
        for r in ArchiMateRelationship.query.filter_by(type="realization").all()
        if r.target_id in goal_by_id
    }
    changes = [
        {
            "id": w.id,
            "name": w.name,
            "status": w.status if w.status in _STATUS_KEYS else "planned",
            "by_when": w.target_date.isoformat() if w.target_date else "",
            "goal": serves.get(w.archimate_element_id) or "",
        }
        for w in WorkPackage.query.order_by(WorkPackage.id).all()
    ]
    return {"goals": goals, "changes": changes, "statuses": list(STATUSES)}


def _save_goal(entry: dict, existing: dict[str, ArchiMateElement], org_id: int) -> ArchiMateElement | None:
    name = _clean(entry.get("name"), _MAX_NAME)
    if not name:
        return None
    element = existing.get(name.lower())
    if element is None:
        element = create_backbone_element(
            element_type="Goal",
            layer="Motivation",
            name=name,
            organization_id=org_id,
            provenance={"source_model": "Goal", "source": "onboarding"},
        )
        existing[name.lower()] = element
    props = dict(element.custom_properties or {})
    for key, value in (("target_date", _date(entry.get("by_when"))), ("measure", _clean(entry.get("measure"), _MAX_MEASURE))):
        if value is not None:
            props[key] = value.isoformat() if isinstance(value, datetime.date) else value
    element.custom_properties = props  # reassigned so the JSON change is tracked
    return element


def _link(change_element: ArchiMateElement, goal: ArchiMateElement) -> bool:
    exists = ArchiMateRelationship.query.filter_by(
        type="realization", source_id=change_element.id, target_id=goal.id
    ).first()
    if exists:
        return True
    ok, _ = ArchiMateRelationshipService.validate_relationship(change_element, goal, "realization")
    if not ok:
        return False
    db.session.add(ArchiMateRelationship(type="realization", source_id=change_element.id, target_id=goal.id))
    db.session.flush()
    return True


def save(goals: list[dict], changes: list[dict], *, org_id: int) -> dict:
    """Create or update goals and changes. Returns counts, including how many links were made."""
    existing = _goal_elements()
    saved_goals = 0
    for entry in goals or []:
        if _save_goal(entry or {}, existing, org_id):
            saved_goals += 1

    saved_changes = linked = 0
    by_name = {(w.name or "").strip().lower(): w for w in WorkPackage.query.all()}
    for entry in changes or []:
        name = _clean((entry or {}).get("name"), 255)
        if not name:
            continue
        work = by_name.get(name.lower())
        if work is None:
            work = WorkPackage(name=name, status="planned", context="enterprise")
            db.session.add(work)
            by_name[name.lower()] = work
        if entry.get("status") in _STATUS_KEYS:
            work.status = entry["status"]
        target = _date(entry.get("by_when"))
        if target is not None:
            work.target_date = target
        db.session.flush()
        sync_archimate_element(work)
        saved_changes += 1

        goal_name = _clean(entry.get("goal"), _MAX_NAME)
        goal = existing.get(goal_name.lower()) if goal_name else None
        if goal is not None and work.archimate_element_id:
            element = db.session.get(ArchiMateElement, work.archimate_element_id)
            if element is not None and _link(element, goal):
                linked += 1
    db.session.commit()
    return {"goals": saved_goals, "changes": saved_changes, "links": linked}
