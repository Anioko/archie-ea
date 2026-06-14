"""Product roadmap service — TPM-011.

Builds a Now/Next/Later horizon view linking Epics to sprint schedule.
"""
import logging
from datetime import date

from app import db

logger = logging.getLogger(__name__)

_VALID_HORIZONS = {"now", "next", "later"}


def _get_models():
    from app.models.models import Requirement
    from app.models.sprint import Sprint
    return Requirement, Sprint


def _sprint_to_dict(sprint) -> dict:
    return {
        "id": sprint.id,
        "name": sprint.name,
        "start_date": sprint.start_date.isoformat() if sprint.start_date else None,
        "end_date": sprint.end_date.isoformat() if sprint.end_date else None,
        "status": sprint.status.value,
    }


def _epic_to_dict(epic, horizon: str | None = None) -> dict:
    total = epic.total_points if hasattr(epic, "total_points") else 0
    completed = epic.completed_points if hasattr(epic, "completed_points") else 0
    pct = round(completed / total * 100) if total > 0 else 0
    return {
        "id": epic.id,
        "title": epic.title or "",
        "total_points": total,
        "completed_points": completed,
        "pct_done": pct,
        "stories_count": epic.stories_count if hasattr(epic, "stories_count") else 0,
        "horizon": horizon or getattr(epic, "horizon", None),
    }


def get_outcome_roadmap(solution_id: int = None, board_id: int = None) -> dict:
    """Return the product roadmap grouped by Now / Next / Later horizons.

    Returns:
        {
            "horizons": {
                "now":   {"epics": [...], "sprints": [...]},
                "next":  {"epics": [...], "sprints": [...]},
                "later": {"epics": [...], "sprints": [...]},
            },
            "unscheduled": [...],
            "total_epics": int,
            "on_track_pct": float,
        }
    """
    Requirement, Sprint = _get_models()

    # ------------------------------------------------------------------
    # 1. Load sprints ordered by start_date
    # ------------------------------------------------------------------
    sprint_query = Sprint.query
    if board_id is not None:
        sprint_query = sprint_query.filter_by(board_id=board_id)
    sprints = sprint_query.order_by(Sprint.start_date.asc().nullslast(), Sprint.id.asc()).all()

    today = date.today()

    # Bucket sprints: now = active/current (index 0-1), next = index 2-3, later = rest
    # Also treat sprints whose end_date >= today as future.
    active_and_future = [
        s for s in sprints
        if s.status.value in ("active", "planning", "review")
        or (s.end_date and s.end_date >= today)
    ]

    now_sprints = active_and_future[:2]
    next_sprints = active_and_future[2:4]
    later_sprints = active_and_future[4:]

    now_ids = {s.id for s in now_sprints}
    next_ids = {s.id for s in next_sprints}
    later_ids = {s.id for s in later_sprints}

    # ------------------------------------------------------------------
    # 2. Load epics with aggregated story data
    # ------------------------------------------------------------------
    epic_query = Requirement.query.filter_by(requirement_type="epic")
    all_epics = epic_query.order_by(Requirement.id).all()

    if not all_epics:
        return _empty_roadmap()

    epic_ids = [e.id for e in all_epics]

    # Aggregate story points per epic in bulk
    from sqlalchemy import func as sa_func
    story_agg = (  # model-safety-ok: single bulk aggregate, not inside loop
        db.session.query(
            Requirement.epic_id,
            sa_func.count(Requirement.id).label("cnt"),
            sa_func.sum(Requirement.story_points).label("total"),
            sa_func.sum(
                db.case((Requirement.dod_complete == True, Requirement.story_points), else_=0)
            ).label("done"),
        )
        .filter(
            Requirement.requirement_type == "story",
            Requirement.epic_id.in_(epic_ids),
        )
        .group_by(Requirement.epic_id)
        .all()
    )

    agg_by_epic: dict = {}
    for row in story_agg:
        agg_by_epic[row.epic_id] = {
            "stories_count": row.cnt or 0,
            "total_points": int(row.total or 0),
            "completed_points": int(row.done or 0),
        }

    # ------------------------------------------------------------------
    # 3. Classify epics into horizons
    # ------------------------------------------------------------------
    horizons: dict = {h: {"epics": [], "sprints": []} for h in ("now", "next", "later")}
    unscheduled: list = []

    for epic in all_epics:
        agg = agg_by_epic.get(epic.id, {"stories_count": 0, "total_points": 0, "completed_points": 0})
        total = agg["total_points"]
        completed = agg["completed_points"]
        pct = round(completed / total * 100) if total > 0 else 0
        entry = {
            "id": epic.id,
            "title": epic.title or "",
            "total_points": total,
            "completed_points": completed,
            "pct_done": pct,
            "stories_count": agg["stories_count"],
            "horizon": getattr(epic, "horizon", None),
        }

        # Determine bucket: explicit horizon column wins; otherwise use sprint membership
        h = getattr(epic, "horizon", None)
        if h in _VALID_HORIZONS:
            horizons[h]["epics"].append(entry)
        else:
            unscheduled.append(entry)

    # ------------------------------------------------------------------
    # 4. Attach sprints to horizon buckets
    # ------------------------------------------------------------------
    horizons["now"]["sprints"] = [_sprint_to_dict(s) for s in now_sprints]
    horizons["next"]["sprints"] = [_sprint_to_dict(s) for s in next_sprints]
    horizons["later"]["sprints"] = [_sprint_to_dict(s) for s in later_sprints]

    # ------------------------------------------------------------------
    # 5. on_track_pct: % of "now" epics with pct_done > 50
    # ------------------------------------------------------------------
    now_epics = horizons["now"]["epics"]
    if now_epics:
        on_track = sum(1 for e in now_epics if e["pct_done"] > 50)
        on_track_pct = round(on_track / len(now_epics) * 100, 1)
    else:
        on_track_pct = 100.0  # vacuously on track when nothing is scheduled

    total_epics = sum(len(horizons[h]["epics"]) for h in _VALID_HORIZONS) + len(unscheduled)

    return {
        "horizons": horizons,
        "unscheduled": unscheduled,
        "total_epics": total_epics,
        "on_track_pct": on_track_pct,
    }


def assign_epic_to_horizon(epic_id: int, horizon: str) -> dict:  # dead-code-ok
    """Assign an epic to a roadmap horizon (now / next / later).

    Passing horizon=None or "" clears the assignment.
    """
    if horizon and horizon not in _VALID_HORIZONS:
        raise ValueError(f"Invalid horizon '{horizon}'. Must be one of: {_VALID_HORIZONS}")

    Requirement, _ = _get_models()
    epic = Requirement.query.filter_by(id=epic_id, requirement_type="epic").first()
    if epic is None:
        raise LookupError(f"Epic {epic_id} not found")

    epic.horizon = horizon or None
    db.session.commit()
    return {"id": epic.id, "horizon": epic.horizon}


def _empty_roadmap() -> dict:
    return {
        "horizons": {
            "now": {"epics": [], "sprints": []},
            "next": {"epics": [], "sprints": []},
            "later": {"epics": [], "sprints": []},
        },
        "unscheduled": [],
        "total_epics": 0,
        "on_track_pct": 100.0,
    }
