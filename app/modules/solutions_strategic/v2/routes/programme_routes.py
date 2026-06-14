"""Transformation Programme governance routes (PROG-001).

Attached to ``solution_design_bp`` (url_prefix=/solutions) — same pattern as
solution_wizard_routes.py. No new blueprint.

Pages:
    GET  /solutions/programmes               — programme portfolio list
    GET  /solutions/programmes/<id>          — governance cockpit

APIs:
    POST   /solutions/programmes                          — create programme
    GET    /solutions/programmes/<id>/api/rollup          — rollup JSON
    POST   /solutions/programmes/<id>/solutions           — assign member solution
    DELETE /solutions/programmes/<id>/solutions/<sid>     — unassign member
    GET    /solutions/programmes/api/unassigned-solutions — picker source
"""

import logging

from flask import jsonify, render_template, request
from flask_login import current_user, login_required

from app import db
from app.models.solution_models import Solution
from app.models.strategic import StrategicInitiative

from .solution_design_routes import solution_design_bp

logger = logging.getLogger(__name__)

VALID_TYPES = ("greenfield", "brownfield")


# =============================================================================
# PAGES
# =============================================================================


@solution_design_bp.route("/programmes", methods=["GET"])
@login_required
def programmes_list():
    """Programme portfolio page."""
    from app.modules.solutions_strategic.v2.services.programme_governance_service import (
        ProgrammeGovernanceService,
    )

    programmes = ProgrammeGovernanceService.list_programmes()
    return render_template("solutions/programmes.html", programmes=programmes)


# ── AI-7: Chief Architect synthesis ──────────────────────────────────── #

@solution_design_bp.route("/<int:solution_id>/review-packet", methods=["GET"])
@login_required
def solution_review_packet(solution_id):
    """Board-ready packet: conformance + decision + readiness for one solution."""
    from app.models.solution_models import Solution
    from app.modules.solutions_strategic.v2.services.chief_architect_service import (
        ChiefArchitectService,
    )

    solution = db.session.get(Solution, solution_id)
    if solution is None:
        return render_template("errors/404.html"), 404
    packet = ChiefArchitectService.solution_packet(solution_id)
    return render_template("solutions/review_packet.html", solution=solution, packet=packet)


@solution_design_bp.route("/<int:solution_id>/review-packet/api", methods=["GET"])
@login_required
def solution_review_packet_api(solution_id):
    from app.modules.solutions_strategic.v2.services.chief_architect_service import (
        ChiefArchitectService,
    )

    packet = ChiefArchitectService.solution_packet(solution_id)
    return jsonify(packet), (200 if packet.get("success") else 404)


@solution_design_bp.route("/architect-synthesis", methods=["GET"])
@login_required
def architect_synthesis():
    """Portfolio-wide Chief Architect synthesis."""
    from app.modules.solutions_strategic.v2.services.chief_architect_service import (
        ChiefArchitectService,
    )

    synthesis = ChiefArchitectService.portfolio_synthesis()
    return render_template("solutions/architect_synthesis.html", synthesis=synthesis)


@solution_design_bp.route("/architect-synthesis/api", methods=["GET"])
@login_required
def architect_synthesis_api():
    from app.modules.solutions_strategic.v2.services.chief_architect_service import (
        ChiefArchitectService,
    )

    return jsonify(ChiefArchitectService.portfolio_synthesis())


# ── AI-6: Escalate an AI finding to the ARB ──────────────────────────── #

@solution_design_bp.route("/arb/escalate", methods=["POST"])
@login_required
def arb_escalate_finding():
    """Turn an AI architect finding into a tracked ARB review item."""
    from app.modules.solutions_strategic.v2.services.arb_escalation_service import (
        ARBEscalationService,
    )

    data = request.get_json(silent=True) or {}
    result = ARBEscalationService.escalate(
        title=data.get("title", ""),
        detail=data.get("detail", ""),
        category=data.get("category", ""),
        severity=data.get("severity", ""),
        user_id=current_user.id,
        solution_id=data.get("solution_id") or None,
    )
    return jsonify(result), (201 if result.get("success") else 400)


# ── AI-5: Data Architecture Stewardship Reviewer ─────────────────────── #

@solution_design_bp.route("/data-stewardship", methods=["GET"])
@login_required
def data_stewardship():
    """AI Data Architect: estate-wide data-layer review."""
    from app.modules.solutions_strategic.v2.services.data_stewardship_reviewer import (
        DataStewardshipReviewer,
    )

    review = DataStewardshipReviewer.review()
    return render_template("solutions/data_stewardship.html", review=review)


@solution_design_bp.route("/data-stewardship/api", methods=["GET"])
@login_required
def data_stewardship_api():
    """Data-stewardship review as JSON (live recompute)."""
    from app.modules.solutions_strategic.v2.services.data_stewardship_reviewer import (
        DataStewardshipReviewer,
    )

    return jsonify(DataStewardshipReviewer.review())


@solution_design_bp.route("/data-stewardship/classify-baseline", methods=["POST"])
@login_required
def data_stewardship_classify():
    """Flag-to-fix: apply a PII-aware baseline classification to unclassified apps."""
    from app.modules.solutions_strategic.v2.services.data_stewardship_reviewer import (
        DataStewardshipReviewer,
    )

    result = DataStewardshipReviewer.apply_baseline_classification(current_user.id)
    return jsonify(result), (200 if result.get("success") else 400)


# ── AI-4: Technical Conformance Reviewer ─────────────────────────────── #

@solution_design_bp.route("/<int:solution_id>/conformance", methods=["GET"])
@login_required
def solution_conformance(solution_id):
    """AI Technical Architect: conformance review against technical policy."""
    from app.models.solution_models import Solution
    from app.modules.solutions_strategic.v2.services.conformance_reviewer import (
        ConformanceReviewer,
    )

    solution = db.session.get(Solution, solution_id)
    if solution is None:
        return render_template("errors/404.html"), 404
    review = ConformanceReviewer.review(solution_id)
    return render_template(
        "solutions/conformance_review.html", solution=solution, review=review,
    )


@solution_design_bp.route("/<int:solution_id>/conformance/api", methods=["GET"])
@login_required
def solution_conformance_api(solution_id):
    """Conformance review as JSON (live recompute)."""
    from app.modules.solutions_strategic.v2.services.conformance_reviewer import (
        ConformanceReviewer,
    )

    review = ConformanceReviewer.review(solution_id)
    return jsonify(review), (200 if review.get("success") else 404)


# ── AI-3: Solution Options Advisor (options + ADR) ───────────────────── #

@solution_design_bp.route("/<int:solution_id>/options-advisor", methods=["GET"])
@login_required
def solution_options(solution_id):
    """AI Solution Architect: options analysis + decision record for a solution."""
    from app.models.solution_models import Solution
    from app.modules.solutions_strategic.v2.services.solution_options_advisor import (
        SolutionOptionsAdvisor,
    )

    solution = db.session.get(Solution, solution_id)
    if solution is None:
        return render_template("errors/404.html"), 404
    latest = SolutionOptionsAdvisor.latest(solution_id)
    return render_template(
        "solutions/options_advisor.html",
        solution=solution,
        adr=SolutionOptionsAdvisor.to_dict(latest) if latest else None,
    )


@solution_design_bp.route("/<int:solution_id>/options-advisor/generate", methods=["POST"])
@login_required
def solution_options_generate(solution_id):
    """Generate options + an ADR via the AI Solution Architect."""
    from app.modules.solutions_strategic.v2.services.solution_options_advisor import (
        SolutionOptionsAdvisor,
    )

    result = SolutionOptionsAdvisor.generate(solution_id, current_user.id)
    return jsonify(result), (201 if result.get("success") else 502)


@solution_design_bp.route("/options-advisor/<int:adr_id>/status", methods=["POST"])
@login_required
def solution_options_status(adr_id):
    """Accept/reject a proposed decision (the human disposes)."""
    from app.modules.solutions_strategic.v2.services.solution_options_advisor import (
        SolutionOptionsAdvisor,
    )

    data = request.get_json(silent=True) or {}
    result = SolutionOptionsAdvisor.set_status(adr_id, data.get("status", ""), current_user.id)
    return jsonify(result), (200 if result.get("success") else 400)


# ── AI-8: Migration Roadmap Advisor (Phase F plateaus) ───────────────── #

@solution_design_bp.route("/<int:solution_id>/migration-roadmap", methods=["GET"])
@login_required
def solution_migration_roadmap(solution_id):
    """AI Solution Architect: TOGAF Phase F transition-plateau roadmap."""
    from app.models.solution_models import Solution
    from app.modules.solutions_strategic.v2.services.migration_roadmap_advisor import (
        MigrationRoadmapAdvisor,
    )

    solution = db.session.get(Solution, solution_id)
    if solution is None:
        return render_template("errors/404.html"), 404
    latest = MigrationRoadmapAdvisor.latest(solution_id)
    return render_template(
        "solutions/migration_roadmap.html",
        solution=solution,
        roadmap=latest.to_dict() if latest else None,
    )


@solution_design_bp.route("/<int:solution_id>/migration-roadmap/generate", methods=["POST"])
@login_required
def solution_migration_roadmap_generate(solution_id):
    """Generate a Phase F migration roadmap via the AI Solution Architect."""
    from app.modules.solutions_strategic.v2.services.migration_roadmap_advisor import (
        MigrationRoadmapAdvisor,
    )

    result = MigrationRoadmapAdvisor.generate(solution_id, current_user.id)
    return jsonify(result), (201 if result.get("success") else 502)


# ── AI-2: Enterprise Architecture Briefing Agent ─────────────────────── #

@solution_design_bp.route("/briefings", methods=["GET"])
@login_required
def ea_briefings():
    """Enterprise Architecture briefing — latest digest + history."""
    from app.modules.solutions_strategic.v2.services.enterprise_briefing_service import (
        EnterpriseBriefingService,
    )

    latest = EnterpriseBriefingService.latest()
    history = EnterpriseBriefingService.history()
    return render_template(
        "solutions/ea_briefing.html",
        latest=latest.to_dict() if latest else None,
        history=[b.to_dict() for b in history],
    )


@solution_design_bp.route("/briefings/<int:briefing_id>", methods=["GET"])
@login_required
def ea_briefing_detail(briefing_id):
    """A specific past briefing."""
    from app.models.strategic import EnterpriseBriefing
    from app.modules.solutions_strategic.v2.services.enterprise_briefing_service import (
        EnterpriseBriefingService,
    )

    b = db.session.get(EnterpriseBriefing, briefing_id)
    if b is None:
        return render_template("errors/404.html"), 404
    return render_template(
        "solutions/ea_briefing.html",
        latest=b.to_dict(),
        history=[x.to_dict() for x in EnterpriseBriefingService.history()],
    )


@solution_design_bp.route("/briefings/api/generate", methods=["POST"])
@login_required
def ea_briefing_generate():
    """Generate a fresh briefing on demand."""
    from app.modules.solutions_strategic.v2.services.enterprise_briefing_service import (
        EnterpriseBriefingService,
    )

    briefing = EnterpriseBriefingService.generate(current_user.id, source="manual")
    # PROG-019: proactively push the flagged findings to the people who can act.
    push = None
    if briefing.flagged_count:
        from app.modules.solutions_strategic.v2.services.governance_notifier import (
            GovernanceNotifier,
        )
        push = GovernanceNotifier.push_findings(
            briefing.findings or [], "EA Briefing", "/solutions/briefings",
            extra_user_ids=[current_user.id],
        )
    return jsonify({"success": True, "briefing": briefing.to_dict(), "push": push}), 201


@solution_design_bp.route("/programmes/<int:initiative_id>/drift", methods=["GET"])
@login_required
def programme_drift(initiative_id):
    """Programme drift history page (PROG-005).

    Renders the cockpit template with show_drift=True so the full snapshot
    table is visible.  No new template required (Rule 1).
    """
    from app.modules.solutions_strategic.v2.services.programme_governance_service import (
        ProgrammeGovernanceService,
    )

    rollup = ProgrammeGovernanceService.rollup(initiative_id)
    if rollup is None:
        return render_template("errors/404.html"), 404
    snapshots = ProgrammeGovernanceService.list_snapshots(initiative_id, limit=50) or []
    return render_template(
        "solutions/programme_cockpit.html",
        rollup=rollup,
        show_drift=True,
        snapshots=snapshots,
    )


@solution_design_bp.route("/programmes/<int:initiative_id>", methods=["GET"])
@login_required
def programme_cockpit(initiative_id):
    """Programme governance cockpit."""
    from app.modules.solutions_strategic.v2.services.programme_governance_service import (
        ProgrammeGovernanceService,
    )

    rollup = ProgrammeGovernanceService.rollup(initiative_id)
    if rollup is None:
        return render_template("errors/404.html"), 404
    # PROG-013: surface the most recent AI-on-contact review (captured at import).
    import_review = None
    for snap in (ProgrammeGovernanceService.list_snapshots(initiative_id, limit=20) or []):
        if snap.get("ai_review"):
            import_review = {**snap["ai_review"], "snapshot_id": snap["id"],
                             "taken_at": snap["taken_at"], "source": snap["source"]}
            break
    return render_template("solutions/programme_cockpit.html", rollup=rollup,
                           import_review=import_review)


# =============================================================================
# APIS
# =============================================================================


@solution_design_bp.route("/programmes", methods=["POST"])
@login_required
def create_programme_entity():
    """Create a Transformation Programme (StrategicInitiative)."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "error": "Programme name is required."}), 400
    itype = (data.get("initiative_type") or "brownfield").lower()
    if itype not in VALID_TYPES:
        return jsonify({"success": False, "error": "initiative_type must be greenfield or brownfield."}), 400

    initiative = StrategicInitiative(
        name=name,
        description=data.get("description") or "",
        initiative_type=itype,
        target_platform=(data.get("target_platform") or "").strip() or None,
        vendor_key=(data.get("vendor_key") or "").strip().upper() or None,
        status=data.get("status") or "in_progress",
        priority=data.get("priority") or "high",
        owner_id=current_user.id,
    )
    db.session.add(initiative)
    db.session.commit()
    logger.info("Programme created: id=%s name=%s type=%s", initiative.id, name, itype)
    return jsonify({"success": True, "id": initiative.id}), 201


@solution_design_bp.route("/programmes/<int:initiative_id>/api/rollup", methods=["GET"])
@login_required
def programme_rollup(initiative_id):
    """Governance rollup as JSON."""
    from app.modules.solutions_strategic.v2.services.programme_governance_service import (
        ProgrammeGovernanceService,
    )

    rollup = ProgrammeGovernanceService.rollup(initiative_id)
    if rollup is None:
        return jsonify({"success": False, "error": "Programme not found."}), 404
    return jsonify({"success": True, **rollup})


@solution_design_bp.route("/programmes/<int:initiative_id>/solutions", methods=["POST"])
@login_required
def programme_assign_solution(initiative_id):
    """Assign an existing solution to the programme."""
    initiative = db.session.get(StrategicInitiative, initiative_id)
    if initiative is None:
        return jsonify({"success": False, "error": "Programme not found."}), 404

    data = request.get_json(silent=True) or {}
    solution_id = data.get("solution_id")
    solution = db.session.get(Solution, solution_id) if solution_id else None
    if solution is None:
        return jsonify({"success": False, "error": "solution_id is required and must exist."}), 400
    if solution.initiative_id and solution.initiative_id != initiative_id:
        return jsonify({
            "success": False,
            "error": f"Solution already belongs to programme {solution.initiative_id}. Unassign it first.",
        }), 409

    solution.initiative_id = initiative_id
    db.session.commit()
    logger.info("Solution %s assigned to programme %s", solution.id, initiative_id)
    return jsonify({"success": True, "solution_id": solution.id})


@solution_design_bp.route(
    "/programmes/<int:initiative_id>/solutions/<int:solution_id>", methods=["DELETE"]
)
@login_required
def programme_unassign_solution(initiative_id, solution_id):
    """Remove a solution from the programme (solution itself is untouched)."""
    solution = db.session.get(Solution, solution_id)
    if solution is None or solution.initiative_id != initiative_id:
        return jsonify({"success": False, "error": "Solution is not a member of this programme."}), 404
    solution.initiative_id = None
    db.session.commit()
    return jsonify({"success": True})


@solution_design_bp.route("/programmes/<int:initiative_id>", methods=["DELETE"])
@login_required
def delete_programme(initiative_id):
    """Delete an EMPTY programme. Programmes with members cannot be deleted —
    unassign the member solutions first (solutions are never touched)."""
    initiative = db.session.get(StrategicInitiative, initiative_id)
    if initiative is None:
        return jsonify({"success": False, "error": "Programme not found."}), 404
    member_count = Solution.query.filter_by(initiative_id=initiative_id).count()
    if member_count:
        return jsonify({
            "success": False,
            "error": f"Programme has {member_count} member solution(s). Unassign them first.",
        }), 409
    db.session.delete(initiative)
    db.session.commit()
    logger.info("Programme %s deleted (was empty)", initiative_id)
    return jsonify({"success": True})


@solution_design_bp.route("/programmes/<int:initiative_id>/fit-gap", methods=["GET"])
@login_required
def programme_fit_gap(initiative_id):
    """Programme fit-gap workbench (PROG-004) — bulk classification across members."""
    from app.models.solution_models import SolutionFitGapEntry
    from app.modules.solutions_strategic.v2.services.programme_governance_service import (
        ProgrammeGovernanceService,
    )

    rollup = ProgrammeGovernanceService.rollup(initiative_id)
    if rollup is None:
        return render_template("errors/404.html"), 404
    entries = ProgrammeGovernanceService.fit_gap_entries(initiative_id) or []
    return render_template(
        "solutions/programme_fit_gap.html",
        rollup=rollup,
        entries=entries,
        fit_types=SolutionFitGapEntry.FIT_TYPES,
        statuses=SolutionFitGapEntry.STATUSES,
    )


@solution_design_bp.route("/programmes/<int:initiative_id>/api/fit-gap", methods=["GET"])
@login_required
def programme_fit_gap_api(initiative_id):
    """Fit-gap entries + per-module rollup as JSON."""
    from app.modules.solutions_strategic.v2.services.programme_governance_service import (
        ProgrammeGovernanceService,
    )

    entries = ProgrammeGovernanceService.fit_gap_entries(initiative_id)
    if entries is None:
        return jsonify({"success": False, "error": "Programme not found."}), 404
    rollup = ProgrammeGovernanceService.rollup(initiative_id)
    return jsonify({"success": True, "entries": entries, "fit_gap": rollup["fit_gap"]})


@solution_design_bp.route("/programmes/<int:initiative_id>/api/fit-gap/bulk", methods=["POST"])
@login_required
def programme_fit_gap_bulk(initiative_id):
    """Bulk reclassify/approve fit-gap entries across member solutions."""
    from app.modules.solutions_strategic.v2.services.programme_governance_service import (
        ProgrammeGovernanceService,
    )

    data = request.get_json(silent=True) or {}
    entry_ids = data.get("entry_ids") or []
    if not entry_ids:
        return jsonify({"success": False, "error": "entry_ids is required and must be non-empty"}), 400
    try:
        result = ProgrammeGovernanceService.bulk_update_fit_gap(
            initiative_id,
            entry_ids,
            fit_type=data.get("fit_type"),
            status=data.get("status"),
            erp_module=data.get("erp_module"),
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, **result})


@solution_design_bp.route("/programmes/<int:initiative_id>", methods=["PATCH"])
@login_required
def update_programme(initiative_id):
    """Update programme governance fields (clean_core_target, status, priority)."""
    initiative = db.session.get(StrategicInitiative, initiative_id)
    if initiative is None:
        return jsonify({"success": False, "error": "Programme not found."}), 404
    data = request.get_json(silent=True) or {}
    if "clean_core_target" in data:
        target = data["clean_core_target"]
        if target in (None, ""):
            initiative.clean_core_target = None
        else:
            try:
                target = int(target)
            except (TypeError, ValueError):
                return jsonify({"success": False, "error": "clean_core_target must be an integer 0-100"}), 400
            if not 0 <= target <= 100:
                return jsonify({"success": False, "error": "clean_core_target must be between 0 and 100"}), 400
            initiative.clean_core_target = target
    if data.get("status"):
        initiative.status = data["status"]
    if data.get("priority"):
        initiative.priority = data["priority"]
    db.session.commit()
    return jsonify({"success": True})


@solution_design_bp.route("/programmes/<int:initiative_id>/api/snapshot", methods=["POST"])
@login_required
def programme_take_snapshot(initiative_id):
    """Capture a governance snapshot + drift check (PROG-005)."""
    from app.modules.solutions_strategic.v2.services.programme_governance_service import (
        ProgrammeGovernanceService,
    )

    snap = ProgrammeGovernanceService.snapshot_programme(
        initiative_id, current_user.id, source="manual"
    )
    if snap is None:
        return jsonify({"success": False, "error": "Programme not found."}), 404
    db.session.commit()
    return jsonify({"success": True, "snapshot": snap}), 201


@solution_design_bp.route("/programmes/<int:initiative_id>/api/snapshots", methods=["GET"])
@login_required
def programme_snapshots(initiative_id):
    """Snapshot history (most recent first)."""
    from app.modules.solutions_strategic.v2.services.programme_governance_service import (
        ProgrammeGovernanceService,
    )

    snaps = ProgrammeGovernanceService.list_snapshots(initiative_id)
    if snaps is None:
        return jsonify({"success": False, "error": "Programme not found."}), 404
    return jsonify({"success": True, "snapshots": snaps})


@solution_design_bp.route(
    "/programmes/<int:initiative_id>/api/snapshots/<int:snapshot_id>", methods=["DELETE"]
)
@login_required
def programme_delete_snapshot(initiative_id, snapshot_id):
    """Delete a snapshot (test hygiene / mistaken captures)."""
    from app.models.strategic import ProgrammeSnapshot

    snap = db.session.get(ProgrammeSnapshot, snapshot_id)
    if snap is None or snap.initiative_id != initiative_id:
        return jsonify({"success": False, "error": "Snapshot not found."}), 404
    db.session.delete(snap)
    db.session.commit()
    return jsonify({"success": True})


@solution_design_bp.route("/programmes/api/list", methods=["GET"])
@login_required
def programmes_api_list():
    """Lightweight programme list for pickers (PROG-002: import job target)."""
    from app.modules.solutions_strategic.v2.services.programme_governance_service import (
        ProgrammeGovernanceService,
    )

    return jsonify({"programmes": ProgrammeGovernanceService.list_programmes()})


@solution_design_bp.route("/programmes/api/unassigned-solutions", methods=["GET"])
@login_required
def programme_unassigned_solutions():
    """Picker source: solutions not yet assigned to any programme."""
    q = (request.args.get("q") or "").strip()
    query = Solution.query.filter(Solution.initiative_id.is_(None))
    if q:
        query = query.filter(Solution.name.ilike(f"%{q}%"))
    rows = query.order_by(Solution.name).limit(20).all()
    return jsonify({
        "results": [
            {
                "id": s.id,
                "name": s.name,
                "adm_phase": (s.adm_phase or "").strip(),
                "governance_status": s.governance_status or "draft",
            }
            for s in rows
        ]
    })
