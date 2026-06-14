import logging

from flask import Blueprint, jsonify, redirect, render_template, request, url_for, flash
from flask_login import current_user, login_required

from app import db
from app.models.architecture_decision import ArchitectureDecision
from app.models.archimate_core import ArchiMateElement
from app.security.audit import audit_logger, AuditEventType, AuditEventSeverity

_log = logging.getLogger(__name__)

arch_decisions_bp = Blueprint("arch_decisions", __name__, url_prefix="/architecture/decisions")


@arch_decisions_bp.route("/")
@login_required
def list_decisions():
    status_filter = request.args.get("status")
    phase_filter = request.args.get("phase")
    query = ArchitectureDecision.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    if phase_filter:
        query = query.filter_by(adm_phase=phase_filter)
    decisions = query.order_by(ArchitectureDecision.created_at.desc()).all()
    return render_template(
        "architecture_decisions/list.html",
        decisions=decisions,
        status_filter=status_filter,
        phase_filter=phase_filter,
    )


@arch_decisions_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_decision():
    if request.method == "POST":
        import json

        decision = ArchitectureDecision(
            decision_id=ArchitectureDecision.next_decision_id(),
            title=request.form.get("title"),
            status=request.form.get("status", "proposed"),
            adm_phase=request.form.get("adm_phase"),
            context=request.form.get("context"),
            decision=request.form.get("decision"),
            consequences=request.form.get("consequences"),
            alternatives=request.form.get("alternatives"),
            archimate_element_ids=json.loads(request.form.get("archimate_element_ids", "[]")),
            created_by_id=current_user.id,
        )
        db.session.add(decision)
        db.session.commit()
        try:
            audit_logger.log_event(
                AuditEventType.DATA_MODIFICATION,
                AuditEventSeverity.MEDIUM,
                "create",
                resource_type="architecture_decision",
                resource_id=str(decision.id),
                details={"decision_id": decision.decision_id, "title": decision.title,
                         "user_id": current_user.id},
                compliance_flags=["SOC2"],
            )
        except Exception as _exc:
            _log.warning("audit log failed for create_decision", _exc)
        flash(f"Architecture Decision {decision.decision_id} created", "success")
        return redirect(url_for("arch_decisions.view_decision", decision_id=decision.id))
    return render_template("architecture_decisions/form.html", decision=None)


@arch_decisions_bp.route("/<int:decision_id>")
@login_required
def view_decision(decision_id):
    decision = ArchitectureDecision.query.get_or_404(decision_id)
    elements = []
    if decision.archimate_element_ids:
        elements = ArchiMateElement.query.filter(
            ArchiMateElement.id.in_(decision.archimate_element_ids)
        ).all()
    return render_template(
        "architecture_decisions/detail.html", decision=decision, elements=elements
    )


@arch_decisions_bp.route("/<int:decision_id>/edit", methods=["GET", "POST"])
@login_required
def edit_decision(decision_id):
    decision = ArchitectureDecision.query.get_or_404(decision_id)
    if request.method == "POST":
        import json

        decision.title = request.form.get("title")
        decision.status = request.form.get("status", "proposed")
        decision.adm_phase = request.form.get("adm_phase")
        decision.context = request.form.get("context")
        decision.decision = request.form.get("decision")
        decision.consequences = request.form.get("consequences")
        decision.alternatives = request.form.get("alternatives")
        decision.archimate_element_ids = json.loads(
            request.form.get("archimate_element_ids", "[]")
        )
        db.session.commit()
        try:
            audit_logger.log_event(
                AuditEventType.DATA_MODIFICATION,
                AuditEventSeverity.MEDIUM,
                "update",
                resource_type="architecture_decision",
                resource_id=str(decision.id),
                details={"decision_id": decision.decision_id, "title": decision.title,
                         "status": decision.status, "user_id": current_user.id},
                compliance_flags=["SOC2"],
            )
        except Exception as _exc:
            _log.warning("audit log failed for edit_decision", _exc)
        flash("Decision updated", "success")
        return redirect(url_for("arch_decisions.view_decision", decision_id=decision.id))
    elements = []
    if decision.archimate_element_ids:
        elements = ArchiMateElement.query.filter(
            ArchiMateElement.id.in_(decision.archimate_element_ids)
        ).all()
    return render_template(
        "architecture_decisions/form.html", decision=decision, selected_elements=elements
    )


@arch_decisions_bp.route("/<int:decision_id>/delete", methods=["POST"])
@login_required
def delete_decision(decision_id):
    decision = ArchitectureDecision.query.get_or_404(decision_id)
    decision_ref = decision.decision_id
    decision_title = decision.title
    db.session.delete(decision)
    db.session.commit()
    try:
        audit_logger.log_event(
            AuditEventType.DATA_MODIFICATION,
            AuditEventSeverity.HIGH,
            "delete",
            resource_type="architecture_decision",
            resource_id=str(decision_id),
            details={"decision_id": decision_ref, "title": decision_title,
                     "user_id": current_user.id},
            compliance_flags=["SOC2"],
        )
    except Exception as _exc:
        _log.warning("audit log failed for delete_decision", _exc)
    flash(f"Architecture Decision {decision_ref} deleted", "success")
    return redirect(url_for("arch_decisions.list_decisions"))



@login_required
def element_search():
    """Search ArchiMate elements for the element picker."""
    q = request.args.get("q", "").strip()
    if not q or len(q) < 2:
        return jsonify([])
    results = (
        ArchiMateElement.query.filter(ArchiMateElement.name.ilike(f"%{q}%"))
        .limit(20)
        .all()
    )
    return jsonify(
        [
            {
                "id": el.id,
                "name": el.name,
                "layer": el.layer if hasattr(el, "layer") else None,
                "element_type": el.element_type if hasattr(el, "element_type") else None,
            }
            for el in results
        ]
    )
