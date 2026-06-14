"""Flow analytics service — cycle time, throughput, lead time, WIP metrics."""
from datetime import datetime, timedelta
from typing import Any


def _get_kanban_card():
    from app.models.adm_kanban import KanbanCard
    return KanbanCard


def _get_history():
    from app.models.kanban_card_history import KanbanCardHistory
    return KanbanCardHistory


def _percentile(sorted_values: list, p: float) -> float:
    """Return the p-th percentile of a sorted list (0–100)."""
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    index = (p / 100.0) * (n - 1)
    lower = int(index)
    upper = min(lower + 1, n - 1)
    frac = index - lower
    return round(sorted_values[lower] * (1 - frac) + sorted_values[upper] * frac, 2)


def get_cycle_time_data(board_id: int, days: int = 90) -> dict[str, Any]:
    """Cycle time = started_at → completed_at for cards on this board.

    Returns dict with average, p50, p85, p95, and per-card data points.
    """
    KanbanCard = _get_kanban_card()
    cutoff = datetime.utcnow() - timedelta(days=days)

    cards = (
        KanbanCard.query
        .filter(
            KanbanCard.board_id == board_id,
            KanbanCard.status == "done",
            KanbanCard.completed_at.isnot(None),
            KanbanCard.started_at.isnot(None),
            KanbanCard.completed_at >= cutoff,
        )
        .all()
    )

    cycle_days_list = []
    data_points = []
    for card in cards:
        delta = (card.completed_at - card.started_at).total_seconds() / 86400.0
        if delta < 0:
            continue
        cycle_days_list.append(delta)
        data_points.append({
            "card_title": card.title,
            "cycle_days": round(delta, 2),
            "completed_at": card.completed_at.isoformat(),
        })

    cycle_days_list.sort()
    average = round(sum(cycle_days_list) / len(cycle_days_list), 2) if cycle_days_list else 0.0

    return {
        "average_cycle_time_days": average,
        "percentile_50": _percentile(cycle_days_list, 50),
        "percentile_85": _percentile(cycle_days_list, 85),
        "percentile_95": _percentile(cycle_days_list, 95),
        "data_points": data_points,
    }


def get_throughput_data(board_id: int, granularity: str = "week") -> dict[str, Any]:
    """Throughput = cards completed per time period.

    granularity: 'week' (default) or 'sprint'.
    Returns periods list and average throughput.
    """
    KanbanCard = _get_kanban_card()

    cards = (
        KanbanCard.query
        .filter(
            KanbanCard.board_id == board_id,
            KanbanCard.status == "done",
            KanbanCard.completed_at.isnot(None),
        )
        .order_by(KanbanCard.completed_at)
        .all()
    )

    if not cards:
        return {"periods": [], "average_throughput": 0.0}

    # Build ISO-week buckets (or 2-week sprint buckets)
    bucket_size_days = 14 if granularity == "sprint" else 7
    earliest = cards[0].completed_at
    latest = cards[-1].completed_at

    buckets: dict[str, int] = {}
    current = earliest.replace(hour=0, minute=0, second=0, microsecond=0)
    while current <= latest + timedelta(days=bucket_size_days):
        label = current.strftime("%Y-W%W") if granularity != "sprint" else current.strftime("%Y-%m-%d")
        buckets[label] = 0
        current += timedelta(days=bucket_size_days)

    for card in cards:
        days_from_start = (card.completed_at - earliest).days
        bucket_index = days_from_start // bucket_size_days
        bucket_start = earliest + timedelta(days=bucket_index * bucket_size_days)
        bucket_start = bucket_start.replace(hour=0, minute=0, second=0, microsecond=0)
        label = bucket_start.strftime("%Y-W%W") if granularity != "sprint" else bucket_start.strftime("%Y-%m-%d")
        if label in buckets:
            buckets[label] += 1

    periods = [{"label": k, "completed": v} for k, v in sorted(buckets.items())]
    non_zero = [p["completed"] for p in periods if p["completed"] > 0]
    average = round(sum(non_zero) / len(non_zero), 2) if non_zero else 0.0

    return {"periods": periods, "average_throughput": average}


def get_lead_time_data(board_id: int, days: int = 90) -> dict[str, Any]:
    """Lead time = created_at → completed_at."""
    KanbanCard = _get_kanban_card()
    cutoff = datetime.utcnow() - timedelta(days=days)

    cards = (
        KanbanCard.query
        .filter(
            KanbanCard.board_id == board_id,
            KanbanCard.status == "done",
            KanbanCard.completed_at.isnot(None),
            KanbanCard.completed_at >= cutoff,
        )
        .all()
    )

    lead_days_list = []
    data_points = []
    for card in cards:
        if card.created_at is None:
            continue
        delta = (card.completed_at - card.created_at).total_seconds() / 86400.0
        if delta < 0:
            continue
        lead_days_list.append(delta)
        data_points.append({
            "card_title": card.title,
            "lead_days": round(delta, 2),
            "completed_at": card.completed_at.isoformat(),
        })

    lead_days_list.sort()
    average = round(sum(lead_days_list) / len(lead_days_list), 2) if lead_days_list else 0.0

    return {
        "average_lead_time_days": average,
        "percentile_50": _percentile(lead_days_list, 50),
        "percentile_85": _percentile(lead_days_list, 85),
        "data_points": data_points,
    }


def get_wip_snapshot(board_id: int) -> dict[str, Any]:
    """WIP snapshot — card count per status column for the board right now."""
    KanbanCard = _get_kanban_card()

    from sqlalchemy import func
    from app import db

    rows = (
        db.session.query(KanbanCard.status, func.count(KanbanCard.id))
        .filter(
            KanbanCard.board_id == board_id,
            KanbanCard.status != "done",
        )
        .group_by(KanbanCard.status)
        .all()
    )

    columns = [{"column": status, "card_count": count} for status, count in rows]
    total = sum(c["card_count"] for c in columns)

    return {"columns": columns, "total_wip": total}


def get_flow_efficiency(board_id: int, days: int = 90) -> dict[str, Any]:
    """Flow efficiency = cycle time / lead time × 100."""
    cycle = get_cycle_time_data(board_id, days)
    lead = get_lead_time_data(board_id, days)

    avg_cycle = cycle["average_cycle_time_days"]
    avg_lead = lead["average_lead_time_days"]

    efficiency = round((avg_cycle / avg_lead * 100), 1) if avg_lead > 0 else 0.0

    return {
        "flow_efficiency_pct": efficiency,
        "average_cycle_time_days": avg_cycle,
        "average_lead_time_days": avg_lead,
    }
