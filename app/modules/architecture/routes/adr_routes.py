"""
ADR (Architecture Decision Record) Routes

Provides UI for managing architecture decisions with ARB workflow.

Routes:
- GET /architecture/adrs - List all ADRs
- GET /architecture/adrs/new - Create new ADR form
- POST /architecture/adrs - Create new ADR
- GET /architecture/adrs/<id> - View ADR detail
- GET /architecture/adrs/<id>/edit - Edit ADR form
- POST /architecture/adrs/<id> - Update ADR
- POST /architecture/adrs/<id>/approve - Approve ADR
- POST /architecture/adrs/<id>/reject - Reject ADR
"""

import logging

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.decorators import admin_required
from app.services.adr_service import ADRService

logger = logging.getLogger(__name__)

adr_bp = Blueprint("adrs", __name__, url_prefix="/architecture/adrs")


@adr_bp.route("/", methods=["GET"])
@login_required
def list_adrs():
    """Redirect to the canonical Architecture Decisions list (S-11).

    Two listings existed over the *same* `architecture_decisions` table:
    this one and `arch_decisions.list_decisions`
    (app/main/routes_architecture_decisions.py). They are backed by two
    model classes mapping that table via `extend_existing` —
    `app/models/architecture_decisions.py:ArchitectureDecision`, used here
    through ADRService, is a plain `db.Model` with **no TenantMixin**, so
    this listing was not tenant-filtered; `app/models/architecture_decision.py`
    (singular), used by `arch_decisions`, carries TenantMixin. That makes
    `arch_decisions.list_decisions` the canonical, tenant-safe listing, and
    it is the one every template links to — nothing linked here.

    The ADR module's remaining routes (create/detail/edit/approve/reject/
    statistics) are untouched; only the duplicate *listing* is retired.
    """
    return redirect(url_for("arch_decisions.list_decisions", **request.args.to_dict()))


@adr_bp.route("/new", methods=["GET"])
@login_required
def new_adr():
    """Show ADR creation form."""
    solution_id = request.args.get("solution_id", type=int)
    decision_type = request.args.get("type", "technology_choice")
    
    templates = ADRService.get_adr_templates()
    template = next((t for t in templates if t['type'] == decision_type), templates[0])
    
    return render_template(
        "architecture/adrs/form.html",
        adr=None,
        template=template,
        decision_types=[(t['type'], t['title'].split(':')[0]) for t in templates],
        solution_id=solution_id
    )


@adr_bp.route("/", methods=["POST"])
@login_required
def create_adr():
    """Create a new ADR."""
    try:
        # Parse alternatives and constraints from form
        alternatives = []
        constraints = []
        
        # Get dynamic form fields (alternatives_*)
        for key in request.form:
            if key.startswith("alt_name_"):
                idx = key.split("_")[-1]
                alt = {
                    "name": request.form.get(f"alt_name_{idx}", ""),
                    "pros": request.form.get(f"alt_pros_{idx}", "").split("\n"),
                    "cons": request.form.get(f"alt_cons_{idx}", "").split("\n"),
                    "rejected_reason": request.form.get(f"alt_reason_{idx}", "")
                }
                alternatives.append(alt)
            elif key.startswith("constraint_name_"):
                idx = key.split("_")[-1]
                constraint = {
                    "constraint_name": request.form.get(f"constraint_name_{idx}", ""),
                    "impact": request.form.get(f"constraint_impact_{idx}", "")
                }
                constraints.append(constraint)
        
        adr = ADRService.create_adr(
            solution_id=int(request.form.get("solution_id", 0)) or None,
            title=request.form["title"],
            context=request.form["context"],
            decision=request.form["decision"],
            rationale=request.form["rationale"],
            decision_type=request.form.get("decision_type", "technology_choice"),
            alternatives=alternatives,
            constraints=constraints,
            consequences=request.form.get("consequences"),
            decided_by_id=current_user.id
        )
        
        flash(f"ADR '{adr.title}' created successfully", "success")
        return redirect(url_for("adrs.view_adr", adr_id=adr.id))
        
    except Exception as e:
        logger.error(f"Failed to create ADR: {e}", exc_info=True)
        flash(f"Failed to create ADR: {str(e)}", "error")
        return redirect(url_for("adrs.new_adr"))


@adr_bp.route("/<int:adr_id>", methods=["GET"])
@login_required
def view_adr(adr_id: int):
    """View ADR detail."""
    adr = ADRService.get_adr(adr_id)
    if not adr:
        flash("ADR not found", "error")
        return redirect(url_for("adrs.list_adrs"))
    
    return render_template("architecture/adrs/detail.html", adr=adr)


@adr_bp.route("/<int:adr_id>/edit", methods=["GET"])
@login_required
def edit_adr(adr_id: int):
    """Show ADR edit form."""
    adr = ADRService.get_adr(adr_id)
    if not adr:
        flash("ADR not found", "error")
        return redirect(url_for("adrs.list_adrs"))
    
    templates = ADRService.get_adr_templates()
    
    return render_template(
        "architecture/adrs/form.html",
        adr=adr,
        template=None,
        decision_types=[(t['type'], t['title'].split(':')[0]) for t in templates]
    )


@adr_bp.route("/<int:adr_id>", methods=["POST"])
@login_required
def update_adr(adr_id: int):
    """Update an existing ADR."""
    try:
        # Parse alternatives and constraints
        alternatives = []
        constraints = []
        
        for key in request.form:
            if key.startswith("alt_name_"):
                idx = key.split("_")[-1]
                alt = {
                    "name": request.form.get(f"alt_name_{idx}", ""),
                    "pros": request.form.get(f"alt_pros_{idx}", "").split("\n"),
                    "cons": request.form.get(f"alt_cons_{idx}", "").split("\n"),
                    "rejected_reason": request.form.get(f"alt_reason_{idx}", "")
                }
                alternatives.append(alt)
            elif key.startswith("constraint_name_"):
                idx = key.split("_")[-1]
                constraint = {
                    "constraint_name": request.form.get(f"constraint_name_{idx}", ""),
                    "impact": request.form.get(f"constraint_impact_{idx}", "")
                }
                constraints.append(constraint)
        
        adr = ADRService.update_adr(
            adr_id=adr_id,
            title=request.form.get("title"),
            context=request.form.get("context"),
            decision=request.form.get("decision"),
            rationale=request.form.get("rationale"),
            alternatives=alternatives,
            constraints=constraints,
            consequences=request.form.get("consequences")
        )
        
        flash(f"ADR '{adr.title}' updated successfully", "success")
        return redirect(url_for("adrs.view_adr", adr_id=adr.id))
        
    except Exception as e:
        logger.error(f"Failed to update ADR {adr_id}: {e}", exc_info=True)
        flash(f"Failed to update ADR: {str(e)}", "error")
        return redirect(url_for("adrs.edit_adr", adr_id=adr_id))


@adr_bp.route("/<int:adr_id>/approve", methods=["POST"])
@login_required
@admin_required
def approve_adr(adr_id: int):
    """Approve an ADR (admin only)."""
    try:
        adr = ADRService.approve_adr(adr_id, current_user.id)
        flash(f"ADR '{adr.title}' approved", "success")
        
        if request.is_json:
            return jsonify({"success": True, "adr": adr.to_dict()})
        return redirect(url_for("adrs.view_adr", adr_id=adr.id))
        
    except Exception as e:
        logger.error(f"Failed to approve ADR {adr_id}: {e}", exc_info=True)
        
        if request.is_json:
            return jsonify({"success": False, "error": str(e)}), 500
        flash(f"Failed to approve ADR: {str(e)}", "error")
        return redirect(url_for("adrs.view_adr", adr_id=adr_id))


@adr_bp.route("/<int:adr_id>/reject", methods=["POST"])
@login_required
@admin_required
def reject_adr(adr_id: int):
    """Reject an ADR (admin only)."""
    try:
        rejection_reason = request.form.get("rejection_reason") or request.json.get("rejection_reason")
        
        if not rejection_reason:
            raise ValueError("Rejection reason is required")
        
        adr = ADRService.reject_adr(adr_id, rejection_reason)
        flash(f"ADR '{adr.title}' rejected", "warning")
        
        if request.is_json:
            return jsonify({"success": True, "adr": adr.to_dict()})
        return redirect(url_for("adrs.view_adr", adr_id=adr.id))
        
    except Exception as e:
        logger.error(f"Failed to reject ADR {adr_id}: {e}", exc_info=True)
        
        if request.is_json:
            return jsonify({"success": False, "error": str(e)}), 500
        flash(f"Failed to reject ADR: {str(e)}", "error")
        return redirect(url_for("adrs.view_adr", adr_id=adr_id))


@adr_bp.route("/statistics", methods=["GET"])
@login_required
def get_statistics():
    """Get ADR statistics (API endpoint)."""
    stats = ADRService.get_adr_statistics()
    return jsonify(stats)
