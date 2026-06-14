"""Flow analytics routes — cycle time, throughput, WIP, and dashboard view."""
import logging

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from app.models.adm_kanban import KanbanBoard

logger = logging.getLogger(__name__)

flow_analytics_bp = Blueprint(
    "flow_analytics",
    __name__,
    url_prefix="",
)


# ── Helper ────────────────────────────────────────────────────────────────────

def _resolve_board(board_id_param) -> tuple:
    """Return (board_id, error_response) from the query-string parameter."""
    board_id = request.args.get("board_id", board_id_param, type=int)
    if not board_id:
        return None, (jsonify({"error": "board_id is required"}), 400)
    board = KanbanBoard.query.get(board_id)
    if not board:
        return None, (jsonify({"error": f"board {board_id} not found"}), 404)
    return board_id, None


# ── API routes ─────────────────────────────────────────────────────────────────

@flow_analytics_bp.route("/api/analytics/cycle-time", methods=["GET"])
@login_required
def api_cycle_time():
    """GET /api/analytics/cycle-time?board_id=N&days=90"""
    from app.services.flow_analytics_service import get_cycle_time_data

    board_id, err = _resolve_board(None)
    if err:
        return err
    days = request.args.get("days", 90, type=int)
    try:
        data = get_cycle_time_data(board_id, days)
    except Exception as exc:
        logger.exception("cycle-time error board=%s", board_id)
        return jsonify({"error": str(exc)}), 500
    return jsonify(data), 200


@flow_analytics_bp.route("/api/analytics/throughput", methods=["GET"])
@login_required
def api_throughput():
    """GET /api/analytics/throughput?board_id=N&granularity=week"""
    from app.services.flow_analytics_service import get_throughput_data

    board_id, err = _resolve_board(None)
    if err:
        return err
    granularity = request.args.get("granularity", "week")
    try:
        data = get_throughput_data(board_id, granularity)
    except Exception as exc:
        logger.exception("throughput error board=%s", board_id)
        return jsonify({"error": str(exc)}), 500
    return jsonify(data), 200


@flow_analytics_bp.route("/api/analytics/lead-time", methods=["GET"])
@login_required
def api_lead_time():
    """GET /api/analytics/lead-time?board_id=N&days=90"""
    from app.services.flow_analytics_service import get_lead_time_data

    board_id, err = _resolve_board(None)
    if err:
        return err
    days = request.args.get("days", 90, type=int)
    try:
        data = get_lead_time_data(board_id, days)
    except Exception as exc:
        logger.exception("lead-time error board=%s", board_id)
        return jsonify({"error": str(exc)}), 500
    return jsonify(data), 200


@flow_analytics_bp.route("/api/analytics/wip", methods=["GET"])
@login_required
def api_wip():
    """GET /api/analytics/wip?board_id=N"""
    from app.services.flow_analytics_service import get_wip_snapshot

    board_id, err = _resolve_board(None)
    if err:
        return err
    try:
        data = get_wip_snapshot(board_id)
    except Exception as exc:
        logger.exception("wip error board=%s", board_id)
        return jsonify({"error": str(exc)}), 500
    return jsonify(data), 200


# ── Page route ─────────────────────────────────────────────────────────────────

@flow_analytics_bp.route("/analytics/flow", methods=["GET"])
@login_required
def flow_analytics_page():
    """GET /analytics/flow — render the flow analytics dashboard."""
    boards = KanbanBoard.query.order_by(KanbanBoard.name).all()
    board_id = request.args.get("board_id", type=int)
    if not board_id and boards:
        board_id = boards[0].id
    return render_template(
        "analytics/flow_analytics.html",
        boards=boards,
        selected_board_id=board_id,
    )
