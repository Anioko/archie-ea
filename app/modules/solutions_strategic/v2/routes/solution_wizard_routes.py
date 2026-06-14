"""Programme wizard routes (ENT-076).

Provides multi-step wizard for guided greenfield/brownfield programme
creation.  Routes are attached to ``solution_design_bp`` (url_prefix=/solutions).
"""

import logging

from flask import jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from .solution_design_routes import solution_design_bp

logger = logging.getLogger(__name__)


# =============================================================================
# WIZARD PAGE
# =============================================================================


@solution_design_bp.route("/new-programme", methods=["GET"])
@login_required
def new_programme():
    """Render the multi-step programme wizard."""
    from app.modules.solutions_strategic.v2.services.programme_setup_service import (
        ProgrammeSetupService,
    )

    service = ProgrammeSetupService()
    templates = service.get_templates()
    return render_template(
        "solutions/programme_wizard.html",
        templates=templates,
    )


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
    """Execute the wizard — create a greenfield or brownfield programme.

    Accepts JSON body with ``mode`` ("greenfield" | "brownfield") plus
    mode-specific fields.  Returns JSON on success with the new solution id
    and a redirect URL.
    """
    from app.modules.solutions_strategic.v2.services.programme_setup_service import (
        ProgrammeSetupService,
    )

    data = request.get_json(silent=True) or {}
    mode = (data.get("mode") or "").lower()

    if mode not in ("greenfield", "brownfield"):
        return jsonify({"success": False, "error": "Invalid mode. Choose greenfield or brownfield."}), 400

    service = ProgrammeSetupService()

    try:
        if mode == "greenfield":
            solution = service.create_greenfield_programme(data, user_id=current_user.id)
        else:
            solution = service.create_brownfield_programme(data, user_id=current_user.id)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        db.session.rollback()
        logger.exception("Programme creation failed: %s", exc)
        return jsonify({"success": False, "error": "An unexpected error occurred. Please try again."}), 500

    return jsonify({
        "success": True,
        "solution_id": solution.id,
        "redirect_url": url_for("solution_design.view_solution", solution_id=solution.id, created="1"),
    })
