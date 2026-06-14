"""Sprint analytics service — burndown and velocity calculations."""
from datetime import date, timedelta

from app.models.sprint import Sprint, SprintStatus


def get_burndown_data(sprint_id: int) -> dict:
    """Return burndown chart data for a sprint.

    Returns:
        {
            "sprint_name": str,
            "start_date": "YYYY-MM-DD",
            "end_date": "YYYY-MM-DD",
            "total_points": int,
            "ideal_line": [{"day": 0, "points": N}, ...],
            "actual_line": [{"day": 0, "points": N}, ...],
            "remaining": int
        }
    """
    sprint = Sprint.query.get(sprint_id)
    if sprint is None:
        return {}

    total_points = sprint.capacity_points or 0
    start = sprint.start_date
    end = sprint.end_date

    if not start or not end or end < start:
        return {
            "sprint_name": sprint.name,
            "start_date": start.isoformat() if start else None,
            "end_date": end.isoformat() if end else None,
            "total_points": total_points,
            "ideal_line": [],
            "actual_line": [],
            "remaining": total_points,
        }

    duration = (end - start).days + 1

    # Ideal line: linear decay from total_points to 0
    ideal_line = []
    for day in range(duration):
        remaining = total_points - round(total_points * day / max(duration - 1, 1))
        ideal_line.append({"day": day, "points": remaining})

    # Actual line: based on completed cards in the sprint's board
    # Cards are associated via story_points; completed_at marks when done
    actual_line = _build_actual_line(sprint, start, end, total_points)

    remaining = actual_line[-1]["points"] if actual_line else total_points

    return {
        "sprint_name": sprint.name,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "total_points": total_points,
        "ideal_line": ideal_line,
        "actual_line": actual_line,
        "remaining": remaining,
    }


def _build_actual_line(sprint: Sprint, start: date, end: date, total_points: int) -> list:
    """Build the actual burndown line from completed cards during the sprint."""
    from app.models.adm_kanban import KanbanCard

    duration = (end - start).days + 1
    today = date.today()

    cards = (
        KanbanCard.query
        .filter_by(board_id=sprint.board_id)
        .filter(KanbanCard.story_points.isnot(None))
        .all()
    )

    # Map: day_offset -> points completed on that day
    completed_per_day: dict[int, int] = {}
    for card in cards:
        if card.completed_at and card.status == "done":
            completed_date = card.completed_at.date() if hasattr(card.completed_at, "date") else card.completed_at
            if start <= completed_date <= end:
                offset = (completed_date - start).days
                completed_per_day[offset] = completed_per_day.get(offset, 0) + (card.story_points or 0)

    actual_line = []
    cumulative_burned = 0
    for day in range(duration):
        if date.today() < start + timedelta(days=day):
            # Future days — stop the actual line here
            break
        cumulative_burned += completed_per_day.get(day, 0)
        remaining = max(0, total_points - cumulative_burned)
        actual_line.append({"day": day, "points": remaining})

    # Always include day 0 if no data
    if not actual_line:
        actual_line = [{"day": 0, "points": total_points}]

    return actual_line


def get_velocity_data(board_id: int = None) -> dict:
    """Return velocity data across closed sprints.

    Returns:
        {
            "sprints": [
                {"name": "Sprint 1", "committed": 21, "completed": 18},
                ...
            ],
            "average_velocity": float
        }
    """
    from app.models.adm_kanban import KanbanCard

    query = Sprint.query.filter_by(status=SprintStatus.CLOSED)
    if board_id:
        query = query.filter_by(board_id=board_id)
    sprints = query.order_by(Sprint.id).all()

    sprint_data = []
    for sprint in sprints:
        committed = sprint.capacity_points or 0
        # Completed points: cards in the board completed within sprint dates
        completed = _sum_completed_points(sprint)
        sprint_data.append({
            "name": sprint.name,
            "committed": committed,
            "completed": completed,
        })

    velocities = [s["completed"] for s in sprint_data]
    average_velocity = (sum(velocities) / len(velocities)) if velocities else 0.0

    return {
        "sprints": sprint_data,
        "average_velocity": round(average_velocity, 1),
    }


def _sum_completed_points(sprint: Sprint) -> int:
    """Sum story_points for cards completed within the sprint date window."""
    from app.models.adm_kanban import KanbanCard

    if not sprint.start_date or not sprint.end_date:
        return 0

    start = sprint.start_date
    end = sprint.end_date

    cards = (
        KanbanCard.query
        .filter_by(board_id=sprint.board_id, status="done")
        .filter(KanbanCard.story_points.isnot(None))
        .filter(KanbanCard.completed_at.isnot(None))
        .all()
    )

    total = 0
    for card in cards:
        completed_date = card.completed_at.date() if hasattr(card.completed_at, "date") else card.completed_at
        if start <= completed_date <= end:
            total += card.story_points or 0
    return total


# =============================================================================
# TPM-009: Sprint throughput, cycle time, and cumulative flow diagram
# =============================================================================


def get_sprint_analytics(sprint_id: int):
    """Compute throughput, cycle time, and CFD for a sprint.

    TPM-009: Returns None if sprint not found.

    Returns dict with:
      - throughput: count of cards completed within sprint date window
      - cycle_time: {"average_days": float, "data_points": [...]}
      - cfd: daily snapshot list of {"date": "YYYY-MM-DD", "backlog": int, "todo": int, "in_progress": int, "review": int, "done": int}
    """
    from app.models.adm_kanban import KanbanCard

    sprint = Sprint.query.get(sprint_id)
    if sprint is None:
        return None

    start = sprint.start_date
    end = sprint.end_date

    # --- Throughput: cards completed within sprint window ---
    throughput = _compute_throughput(sprint, start, end)

    # --- Cycle time: mean days from started_at to completed_at ---
    cycle_time = _compute_cycle_time(sprint, start, end)

    # --- CFD: daily card count per status column ---
    cfd = _compute_cfd(sprint, start, end)

    return {
        "sprint_id": sprint_id,
        "sprint_name": sprint.name,
        "start_date": start.isoformat() if start else None,
        "end_date": end.isoformat() if end else None,
        "throughput": throughput,
        "cycle_time": cycle_time,
        "cfd": cfd,
    }


def _compute_throughput(sprint, start, end) -> int:
    """Count cards moved to done within the sprint date window."""
    from app.models.adm_kanban import KanbanCard

    if not sprint.board_id or not start or not end:
        return 0

    cards = (
        KanbanCard.query
        .filter_by(board_id=sprint.board_id, status="done")
        .filter(KanbanCard.completed_at.isnot(None))
        .all()
    )
    count = 0
    for card in cards:
        completed_date = card.completed_at.date() if hasattr(card.completed_at, "date") else card.completed_at
        if start <= completed_date <= end:
            count += 1
    return count


def _compute_cycle_time(sprint, start, end) -> dict:
    """Compute mean cycle time (started_at → completed_at) for cards done in sprint."""
    from app.models.adm_kanban import KanbanCard

    if not sprint.board_id or not start or not end:
        return {"average_days": 0.0, "data_points": []}

    cards = (
        KanbanCard.query
        .filter_by(board_id=sprint.board_id, status="done")
        .filter(KanbanCard.completed_at.isnot(None))
        .filter(KanbanCard.started_at.isnot(None))
        .all()
    )
    cycle_days = []
    data_points = []
    for card in cards:
        completed_date = card.completed_at.date() if hasattr(card.completed_at, "date") else card.completed_at
        if start <= completed_date <= end:
            delta = (card.completed_at - card.started_at).total_seconds() / 86400.0
            if delta >= 0:
                cycle_days.append(delta)
                data_points.append({
                    "card_id": card.id,
                    "title": card.title,
                    "cycle_days": round(delta, 2),
                })

    average = round(sum(cycle_days) / len(cycle_days), 2) if cycle_days else 0.0
    return {"average_days": average, "data_points": data_points}


def _compute_cfd(sprint, start, end) -> list:
    """Build a cumulative flow diagram snapshot: daily card counts per status column."""
    from app.models.adm_kanban import KanbanCard

    if not sprint.board_id or not start or not end:
        return []

    all_cards = KanbanCard.query.filter_by(board_id=sprint.board_id).all()
    _COLUMNS = ["backlog", "todo", "in_progress", "review", "done"]

    cfd = []
    today = date.today()
    current = start
    while current <= min(end, today):
        snapshot = {col: 0 for col in _COLUMNS}
        snapshot["date"] = current.isoformat()
        for card in all_cards:
            # Determine what status the card was in on `current` date
            created = card.created_at.date() if card.created_at and hasattr(card.created_at, "date") else card.created_at
            if created and created > current:
                continue  # card didn't exist yet
            completed = card.completed_at.date() if card.completed_at and hasattr(card.completed_at, "date") else card.completed_at
            started = card.started_at.date() if card.started_at and hasattr(card.started_at, "date") else card.started_at
            if completed and completed <= current:
                col = "done"
            elif started and started <= current:
                col = "in_progress"
            elif created and created <= current:
                col = card.status if card.status in _COLUMNS else "backlog"
            else:
                continue
            snapshot[col] = snapshot.get(col, 0) + 1
        cfd.append(snapshot)
        current = current + timedelta(days=1)

    return cfd
