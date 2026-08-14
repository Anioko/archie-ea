"""Stakeholder Map — Power/Interest Grid routes."""
import logging

from flask import Blueprint, g, jsonify, render_template, request

from app import db
from app.models.solution_stakeholder import SolutionStakeholder, SolutionStakeholderMapping
from app.modules.architecture.services.stakeholder_service import StakeholderService
from app.services.feature_flag_service import FeatureFlagService
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
        User.organization_id == g.current_org_id,
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

    try:
        influence_level = int(data.get("influence_level", 3))
        interest_level = int(data.get("interest_level", 3))
        business_actor_id = int(business_actor_id) if business_actor_id else None
        user_id = int(user_id) if user_id else None
    except (ValueError, TypeError):
        return jsonify({"error": "influence_level, interest_level, business_actor_id and user_id must be integers"}), 400

    s = SolutionStakeholder(
        name=data.get("name", "New Stakeholder"),
        description=data.get("description", ""),
        influence_level=influence_level,
        interest_level=interest_level,
        business_actor_id=business_actor_id,
        user_id=user_id,
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
        try:
            solution_id = int(solution_id)
        except (ValueError, TypeError):
            db.session.rollback()
            return jsonify({"error": "solution_id must be an integer"}), 400
        mapping = SolutionStakeholderMapping(
            stakeholder_id=s.id,
            solution_id=solution_id,
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

    try:
        if "influence_level" in data:
            s.influence_level = max(1, min(5, int(data["influence_level"])))
        if "interest_level" in data:
            s.interest_level = max(1, min(5, int(data["interest_level"])))
    except (ValueError, TypeError):
        return jsonify({"error": "influence_level and interest_level must be integers"}), 400
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


# ---------------------------------------------------------------------------
# AI
# ---------------------------------------------------------------------------

MAX_BUSINESS_CONTEXT_CHARS = 8000


@stakeholder_map_api_bp.route("/ai/identify", methods=["POST"])
@login_required
def ai_identify_stakeholders():
    """POST /api/stakeholders/ai/identify
    Body: {"business_context": "..."}
    Suggests stakeholders from free-text context via the LLM. Suggestions are
    NOT persisted — the caller reviews them and adds the ones it wants via the
    existing POST /api/stakeholders/ endpoint.
    """
    feature_guard = FeatureFlagService.require_ai_for_route(
        FeatureFlagService.FEATURE_SUGGESTIONS, endpoint_name="stakeholder_map_api.ai_identify_stakeholders"
    )
    if feature_guard:
        return feature_guard

    data = request.get_json(force=True) or {}
    business_context = (data.get("business_context") or "").strip()
    if not business_context:
        return jsonify({"error": "business_context is required"}), 400
    if len(business_context) > MAX_BUSINESS_CONTEXT_CHARS:
        return jsonify({
            "error": f"business_context is too long (max {MAX_BUSINESS_CONTEXT_CHARS} characters)"
        }), 400

    try:
        suggestions = StakeholderService().identify_stakeholders_from_context(business_context)
    except Exception as e:
        logger.exception("AI stakeholder identification failed")
        return jsonify({"error": f"Stakeholder identification failed: {e}"}), 502

    return jsonify({"stakeholders": suggestions})


@stakeholder_map_api_bp.route("/<int:stakeholder_id>/ai/engagement-strategy", methods=["POST"])
@login_required
def ai_engagement_strategy(stakeholder_id):
    """POST /api/stakeholders/<id>/ai/engagement-strategy
    Recommends a tailored engagement strategy for an existing stakeholder,
    using their recorded description/concerns/attitude and their current
    Power/Interest grid position.
    """
    feature_guard = FeatureFlagService.require_ai_for_route(
        FeatureFlagService.FEATURE_SUGGESTIONS, endpoint_name="stakeholder_map_api.ai_engagement_strategy"
    )
    if feature_guard:
        return feature_guard

    stakeholder = SolutionStakeholder.query.get_or_404(stakeholder_id)

    try:
        strategy = StakeholderService().recommend_engagement_strategy_for_solution_stakeholder(
            stakeholder
        )
    except Exception as e:
        logger.exception(
            "AI engagement strategy recommendation failed for stakeholder %s", stakeholder_id
        )
        return jsonify({"error": f"Engagement strategy recommendation failed: {e}"}), 502

    return jsonify(strategy)
