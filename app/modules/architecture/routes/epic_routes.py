"""Epic hierarchy REST API — /api/epics."""
import logging

from flask import Blueprint, jsonify, render_template, request

from app.services import epic_hierarchy_service
from flask_login import login_required

logger = logging.getLogger(__name__)

epic_bp = Blueprint("epic_bp", __name__, url_prefix="/api/epics")
epic_ui_bp = Blueprint("epic_ui_bp", __name__)


# ---------------------------------------------------------------------------
# UI route
# ---------------------------------------------------------------------------


@epic_ui_bp.route("/epics/hierarchy")
@login_required
def epic_hierarchy_page():
    """GET /epics/hierarchy — render the hierarchy tree template."""
    solution_id = request.args.get("solution_id", type=int)
    tree = epic_hierarchy_service.get_epic_tree(solution_id=solution_id)
    return render_template("epics/epic_hierarchy.html", tree=tree)


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------


@epic_bp.route("", methods=["POST"])
@login_required
def create_epic():
    """POST /api/epics — create a new epic. Returns 201."""
    data = request.get_json(force=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    epic = epic_hierarchy_service.create_epic(
        title=title,
        description=data.get("description", ""),
        solution_id=data.get("solution_id"),
    )
    return jsonify(epic), 201


@epic_bp.route("", methods=["GET"])
@login_required
def list_epics():
    """GET /api/epics?solution_id=N — list epics with tree."""
    solution_id = request.args.get("solution_id", type=int)
    tree = epic_hierarchy_service.get_epic_tree(solution_id=solution_id)
    return jsonify(tree), 200


@epic_bp.route("/<int:epic_id>/stories", methods=["POST"])
@login_required
def create_story(epic_id: int):
    """POST /api/epics/<id>/stories — create a story under the epic. Returns 201."""
    data = request.get_json(force=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    story = epic_hierarchy_service.create_story(
        title=title,
        epic_id=epic_id,
        story_points=data.get("story_points", 0),
    )
    return jsonify(story), 201


@epic_bp.route("/<int:epic_id>/tree", methods=["GET"])
@login_required
def get_epic_tree(epic_id: int):
    """GET /api/epics/<id>/tree — full hierarchy JSON for one epic."""
    tree = epic_hierarchy_service.get_epic_tree()
    for node in tree:
        if node["id"] == epic_id:
            return jsonify(node), 200
    return jsonify({"error": "Epic not found"}), 404


@epic_bp.route("/<int:epic_id>/stories/<int:story_id>/subtasks", methods=["POST"])
@login_required
def create_subtask(epic_id: int, story_id: int):
    """POST /api/epics/<epic_id>/stories/<story_id>/subtasks — create sub-task. Returns 201."""
    data = request.get_json(force=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    subtask = epic_hierarchy_service.create_subtask(
        title=title,
        parent_story_id=story_id,
    )
    return jsonify(subtask), 201
