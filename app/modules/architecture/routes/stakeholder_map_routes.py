"""Stakeholder Map — Power/Interest Grid routes."""
import logging

from flask import Blueprint, jsonify, render_template, request

from app import db
from app.models.solution_stakeholder import SolutionStakeholder, SolutionStakeholderMapping
from flask_login import login_required

logger = logging.getLogger(__name__)

stakeholder_map_ui_bp = Blueprint("stakeholder_map", __name__)
stakeholder_map_api_bp = Blueprint("stakeholder_map_api", __name__, url_prefix="/api/stakeholders")


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

@stakeholder_map_ui_bp.route("/stakeholders/map")
@login_required
def stakeholder_map_page():
    """GET /stakeholders/map — Power/Interest grid canvas."""
    from app.models.solution_models import Solution
    solutions = Solution.query.order_by(Solution.name).all()
    return render_template(
        "stakeholders/map.html",
        solutions=solutions,
    )


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@stakeholder_map_api_bp.route("/map-data")
@login_required
def map_data():
    """GET /api/stakeholders/map-data?solution_id=<id>
    Returns stakeholder list serialised for the D3 scatter canvas.
    """
    solution_id = request.args.get("solution_id", type=int)

    if solution_id:
        # Stakeholders linked to this solution via mapping table
        linked_ids = db.session.query(SolutionStakeholderMapping.stakeholder_id).filter_by(
            solution_id=solution_id
        ).subquery()
        stakeholders = SolutionStakeholder.query.filter(
            SolutionStakeholder.id.in_(linked_ids)
        ).all()
        # Fallback: return all if none linked
        if not stakeholders:
            stakeholders = SolutionStakeholder.query.limit(500).all()
    else:
        stakeholders = SolutionStakeholder.query.limit(500).all()

    return jsonify([s.to_dict(include_details=False) for s in stakeholders])


@stakeholder_map_api_bp.route("/search-people")
@login_required
def search_people():
    """GET /api/stakeholders/search-people?q=<query>
    Search BusinessActors and Users to pick as stakeholders.
    Returns canonical entities, not standalone stakeholder records.
    """
    from app.models.business_layer import BusinessActor
    from app.models.user import User

    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])

    results = []

    # Search BusinessActors (org units, departments, roles, people)
    actors = BusinessActor.query.filter(
        BusinessActor.name.ilike(f"%{q}%")
    ).limit(10).all()
    for a in actors:
        results.append({
            "id": a.id, "name": a.name, "source": "business_actor",
            "type": getattr(a, "actor_type", "Organization"),
            "department": getattr(a, "department", "") or "",
        })

    # Search Users
    users = User.query.filter(
        db.or_(
            User.first_name.ilike(f"%{q}%"),
            User.last_name.ilike(f"%{q}%"),
            User.email.ilike(f"%{q}%"),
        )
    ).limit(10).all()
    for u in users:
        results.append({
            "id": u.id, "name": u.full_name(), "source": "user",
            "type": "Individual", "department": "",
        })

    return jsonify(results)


@stakeholder_map_api_bp.route("/", methods=["POST"])
@login_required
def create_stakeholder():
    """POST /api/stakeholders/ — Create or link a stakeholder.

    If business_actor_id or user_id is provided, links to the canonical entity.
    Otherwise creates a standalone record (backward compatible).
    """
    data = request.get_json(force=True) or {}
    from app.models.solution_stakeholder import StakeholderType, StakeholderAttitude

    # Check if linking to existing entity
    business_actor_id = data.get("business_actor_id")
    user_id = data.get("user_id")

    s = SolutionStakeholder(
        name=data.get("name", "New Stakeholder"),
        description=data.get("description", ""),
        influence_level=int(data.get("influence_level", 3)),
        interest_level=int(data.get("interest_level", 3)),
        business_actor_id=int(business_actor_id) if business_actor_id else None,
        user_id=int(user_id) if user_id else None,
    )
    try:
        s.stakeholder_type = StakeholderType(data.get("stakeholder_type", "individual"))
    except ValueError:
        s.stakeholder_type = StakeholderType.INDIVIDUAL
    try:
        s.attitude = StakeholderAttitude(data.get("attitude", "neutral"))
    except ValueError:
        s.attitude = StakeholderAttitude.NEUTRAL

    db.session.add(s)
    db.session.flush()

    # Link to solution if provided
    solution_id = data.get("solution_id")
    if solution_id:
        mapping = SolutionStakeholderMapping(
            stakeholder_id=s.id,
            solution_id=int(solution_id),
        )
        db.session.add(mapping)

    db.session.commit()
    return jsonify(s.to_dict(include_details=False)), 201


@stakeholder_map_api_bp.route("/<int:stakeholder_id>", methods=["PATCH"])
@login_required
def update_stakeholder(stakeholder_id):
    """PATCH /api/stakeholders/<id> — Update position or attributes."""
    s = SolutionStakeholder.query.get_or_404(stakeholder_id)
    data = request.get_json(force=True) or {}

    if "influence_level" in data:
        s.influence_level = max(1, min(5, int(data["influence_level"])))
    if "interest_level" in data:
        s.interest_level = max(1, min(5, int(data["interest_level"])))
    if "attitude" in data:
        from app.models.solution_stakeholder import StakeholderAttitude
        try:
            s.attitude = StakeholderAttitude(data["attitude"])
        except ValueError:
            logger.exception("Failed to compute s.attitude")
            pass
    if "name" in data:
        s.name = data["name"]

    db.session.commit()
    return jsonify(s.to_dict(include_details=False))
