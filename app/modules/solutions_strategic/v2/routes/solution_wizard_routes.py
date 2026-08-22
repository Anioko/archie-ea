"""Programme wizard routes (ENT-076).

Provides multi-step wizard for guided greenfield/brownfield programme
creation.  Routes are attached to ``solution_design_bp`` (url_prefix=/solutions).
"""

import logging
import uuid
from datetime import date

from flask import g, jsonify, render_template, request
from flask_login import current_user, login_required

from .solution_design_routes import solution_design_bp

logger = logging.getLogger(__name__)


# =============================================================================
# WIZARD PAGE
# =============================================================================


@solution_design_bp.route("/new-programme", methods=["GET"])
@login_required
def new_programme():
    """Render the canonical business-first programme intake."""
    return render_template("solutions/programme_wizard.html")


# =============================================================================
# TEMPLATES API
# =============================================================================


@solution_design_bp.route("/programme-templates", methods=["GET"])
@login_required
def programme_templates():
    """Return available programme templates as JSON."""
    from app.modules.solutions_strategic.v2.services.programme_setup_service import (
        ProgrammeSetupService,
    )

    service = ProgrammeSetupService()
    return jsonify({"templates": service.get_templates()})


# =============================================================================
# CREATE PROGRAMME
# =============================================================================


@solution_design_bp.route("/create-programme", methods=["POST"])
@login_required
def create_programme():
    """Create the canonical business-first programme aggregate."""
    from app.modules.solutions_strategic.v2.services.programme_setup_service import (
        ProgrammeSetupService,
    )
    from app.modules.transformation_room.domain import ActorContext, ProgrammeIntake, TransformationError

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "JSON object required."}), 400
    forbidden = {
        "organization_id",
        "created_by_id",
        "decision_by_id",
        "status",
        "lifecycle_status",
        "lifecycle_stage",
        "review_status",
        "solution_id",
    }
    supplied_forbidden = sorted(forbidden.intersection(data))
    if supplied_forbidden:
        return jsonify(
            {
                "success": False,
                "error": "Server-owned identity and lifecycle fields are not accepted.",
                "fields": supplied_forbidden,
            }
        ), 400
    command_key = (request.headers.get("Idempotency-Key") or "").strip()
    if not command_key:
        return jsonify({"success": False, "error": "Idempotency-Key header is required."}), 400
    organization_id = getattr(g, "current_org_id", None)
    if organization_id is None:
        return jsonify({"success": False, "error": "An active organization is required."}), 401
    runtime_roles = {
        role
        for role in (
            getattr(current_user, "enterprise_role", None),
            "organization_admin" if getattr(current_user, "is_org_admin", False) else None,
            "platform_admin" if getattr(current_user, "is_platform_admin", False) else None,
        )
        if role
    }
    actor = ActorContext(
        user_id=current_user.id,
        organization_id=organization_id,
        roles=frozenset(runtime_roles),
        request_id=request.headers.get("X-Request-ID") or str(uuid.uuid4()),
    )

    try:
        target_date = data.get("target_date")
        intake = ProgrammeIntake(
            name=data.get("name") or "",
            objective=data.get("objective") or "",
            owner_id=data.get("owner_id"),
            target_date=date.fromisoformat(target_date) if target_date else None,
            target_date_unavailable_reason=data.get("target_date_unavailable_reason"),
            workstream_type=data.get("workstream_type") or "application_rationalisation",
            scope_expression=data.get("scope_expression") or {},
            outcome=data.get("outcome") or {},
        )
        result = ProgrammeSetupService.create_business_first_programme(
            actor=actor,
            command_key=command_key,
            request=intake,
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except TransformationError as exc:
        return jsonify({"success": False, "error": exc.reason, "code": exc.code}), exc.http_status
    except Exception as exc:
        logger.exception("Programme creation failed: %s", exc)
        return jsonify({"success": False, "error": "An unexpected error occurred. Please try again."}), 500

    programme_id = result.object_ids["programme_id"]
    workstream_id = result.object_ids["workstream_id"]
    response = jsonify(
        {
            "success": True,
            "programme_id": programme_id,
            "workstream_id": workstream_id,
            "outcome_commitment_id": result.object_ids["outcome_commitment_id"],
            "operation_result_id": result.operation_result_id,
            "redirect_url": (
                f"/solutions/programmes/{programme_id}/workstreams/{workstream_id}/objective"
            ),
        }
    )
    response.status_code = 201 if result.created else 200
    return response
