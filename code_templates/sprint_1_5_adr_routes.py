"""
ADR API Routes
Sprint 1.5: ADR Generation

File: app/routes/adr_routes.py
"""

from flask import Blueprint, Response, jsonify, request
from flask_login import current_user, login_required

from app.auth.decorators import requires_permission
from app.middleware.rate_limiter import AI_HEAVY_LIMIT, LIGHT_LIMIT, limiter
from app.services.adr_service import ADRService

bp = Blueprint("adr", __name__, url_prefix="/api/adr")
adr_service = ADRService()


@bp.route("/generate", methods=["POST"])
@limiter.limit(AI_HEAVY_LIMIT)  # 10 per minute (AI-heavy)
@login_required
@requires_permission("adr.create")
def generate_adr():
    """Generate ADR from architecture session"""
    data = request.json
    session_id = data.get("session_id")

    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    try:
        adr = adr_service.generate_adr_from_session(
            session_id=session_id, tenant_id=current_user.tenant_id, user_id=current_user.id
        )

        return (
            jsonify(
                {
                    "adr_id": adr.id,
                    "adr_number": adr.adr_number,
                    "title": adr.title,
                    "status": adr.status,
                }
            ),
            201,
        )

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"ADR generation failed: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/<int:adr_id>", methods=["GET"])
@limiter.limit(LIGHT_LIMIT)  # 100 per minute
@login_required
@requires_permission("adr.view")
def get_adr(adr_id):
    """Get ADR by ID"""
    try:
        adr = adr_service._get_adr(adr_id, current_user.tenant_id)
        return jsonify(adr.to_dict()), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@bp.route("/<int:adr_id>/export", methods=["GET"])
@limiter.limit(LIGHT_LIMIT)
@login_required
@requires_permission("adr.export")
def export_adr(adr_id):
    """Export ADR in various formats"""
    format_type = request.args.get("format", "markdown")

    try:
        if format_type == "markdown":
            content = adr_service.export_adr_markdown(adr_id, current_user.tenant_id)
            return Response(
                content,
                mimetype="text/markdown",
                headers={"Content-Disposition": f"attachment; filename=ADR-{adr_id:04d}.md"},
            )
        else:
            return jsonify({"error": "Unsupported format"}), 400

    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@bp.route("/", methods=["GET"])
@limiter.limit(LIGHT_LIMIT)
@login_required
@requires_permission("adr.view")
def list_adrs():
    """List ADRs for tenant"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    status = request.args.get("status")

    from app.models.adr_models import ArchitectureDecisionRecord

    query = db.session.query(ArchitectureDecisionRecord).filter_by(tenant_id=current_user.tenant_id)

    if status:
        query = query.filter_by(status=status)

    pagination = query.order_by(ArchitectureDecisionRecord.adr_number.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return (
        jsonify(
            {
                "adrs": [adr.to_dict() for adr in pagination.items],
                "total": pagination.total,
                "page": page,
                "per_page": per_page,
                "pages": pagination.pages,
            }
        ),
        200,
    )
