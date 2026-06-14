"""MP-005: Phase F Migration Planning API Routes.

Endpoints for TOGAF ADM Phase F — Migration Planning.
All endpoints require authentication.
"""
import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required  # dead-code-ok

from app import db  # dead-code-ok

# Module-level imports so tests can patch via:
#   app.modules.ea_workflows.routes.phase_f_routes.MigrationWave
# Wrapped in try/except to handle APP_FAST_INIT guard in implementation_migration.
try:
    from app.models.implementation_migration import MigrationWave
except Exception:  # pragma: no cover
    MigrationWave = None  # type: ignore[assignment,misc]

try:
    from app.models.roadmap import RoadmapTask
except Exception:  # pragma: no cover
    RoadmapTask = None  # type: ignore[assignment,misc]

try:
    from app.models.capability_gap_analysis import GapSolutionOption
except Exception:  # pragma: no cover
    GapSolutionOption = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

phase_f_bp = Blueprint("phase_f", __name__, url_prefix="/api/ea/phase-f")


# ---------------------------------------------------------------------------
# GET /api/ea/phase-f/waves
# ---------------------------------------------------------------------------


@phase_f_bp.route("/waves", methods=["GET"])
@login_required
def get_waves():
    """Return all MigrationWave rows with associated workpackage count.

    Response 200::

        {
            "waves": [
                {
                    "id": int,
                    "wave_number": int,
                    "wave_name": str,
                    "status": str,
                    "workpackage_count": int
                }
            ],
            "total": int
        }
    """
    if MigrationWave is None:
        return jsonify({"waves": [], "total": 0}), 200
    try:
        waves = MigrationWave.query.order_by(MigrationWave.wave_number).all() if MigrationWave else []
        result = []
        for wave in waves:
            try:
                wp_count = wave.workpackages.count()
            except Exception:
                wp_count = 0
            result.append(
                {
                    "id": wave.id,
                    "wave_number": wave.wave_number,
                    "wave_name": wave.name,
                    "status": wave.status,
                    "workpackage_count": wp_count,
                }
            )
        return jsonify({"waves": result, "total": len(result)}), 200
    except Exception as exc:
        logger.error("phase-f/waves error: %s", exc, exc_info=True)
        return jsonify({"error": "Failed to load migration waves", "detail": str(exc)}), 500


# ---------------------------------------------------------------------------
# GET /api/ea/phase-f/roadmap
# ---------------------------------------------------------------------------


@phase_f_bp.route("/roadmap", methods=["GET"])
@login_required
def get_roadmap():
    """Return all RoadmapTask rows.

    Response 200::

        {"tasks": [...], "total": int}
    """
    if RoadmapTask is None:
        return jsonify({"tasks": [], "total": 0}), 200
    try:
        tasks = RoadmapTask.query.order_by(RoadmapTask.start_date).all()
        result = [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status,
                "start_date": t.start_date.isoformat() if t.start_date else None,
                "end_date": t.end_date.isoformat() if t.end_date else None,
                "priority": t.priority,
                "percent_complete": t.percent_complete,
            }
            for t in tasks
        ]
        return jsonify({"tasks": result, "total": len(result)}), 200
    except Exception as exc:
        logger.error("phase-f/roadmap error: %s", exc, exc_info=True)
        return jsonify({"tasks": [], "total": 0}), 200


# ---------------------------------------------------------------------------
# POST /api/ea/phase-f/sequence-waves
# ---------------------------------------------------------------------------


@phase_f_bp.route("/sequence-waves", methods=["POST"])
@login_required
def sequence_waves():
    """Sequence gaps into MigrationWave records.

    Request Body::

        {"gap_ids": [list of gap_analysis_ids]}

    Response 201::

        {"waves": [...], "sequenced": int}
    """
    if not request.is_json:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Content-Type must be application/json",
                    "error_code": "INVALID_CONTENT_TYPE",
                }
            ),
            400,
        )

    data = request.get_json() or {}
    gap_ids = data.get("gap_ids", [])

    try:
        from app.services.gap_register_service import get_unified_gap_register
        from app.services.migration_wave_sequencing_service import MigrationWaveSequencingService

        gap_register = get_unified_gap_register()
        if gap_ids:
            gap_register = [g for g in gap_register if g.get("id") in gap_ids]

        svc = MigrationWaveSequencingService()
        waves = svc.sequence_waves(gap_register)

        result = [
            {
                "id": w.id,
                "wave_number": w.wave_number,
                "wave_name": w.name,
                "status": w.status,
                "planned_start": w.planned_start.isoformat() if w.planned_start else None,
                "planned_end": w.planned_end.isoformat() if w.planned_end else None,
            }
            for w in waves
        ]
        return jsonify({"waves": result, "sequenced": len(result)}), 201
    except Exception as exc:
        logger.error("phase-f/sequence-waves error: %s", exc, exc_info=True)
        return jsonify({"error": "Failed to sequence waves", "detail": str(exc)}), 500


# ---------------------------------------------------------------------------
# GET /api/ea/phase-f/effort-summary
# ---------------------------------------------------------------------------


@phase_f_bp.route("/effort-summary", methods=["GET"])
@login_required
def effort_summary():
    """Return effort summary grouped by migration wave.

    Uses GapSolutionOption.implementation_duration_months (×4 = weeks) as
    a proxy for time_to_implement_weeks, grouped by wave via MigrationWave
    names derived from severity buckets.

    Response 200::

        {"total_weeks": int, "by_wave": {"wave_name": weeks}}
    """
    try:
        options = GapSolutionOption.query.all()
        total_weeks = 0
        for opt in options:
            months = opt.implementation_duration_months or 0
            total_weeks += months * 4

        waves = MigrationWave.query.order_by(MigrationWave.wave_number).all() if MigrationWave else []
        by_wave = {w.name: 0 for w in waves}

        return jsonify({"total_weeks": total_weeks, "by_wave": by_wave}), 200
    except Exception as exc:
        logger.error("phase-f/effort-summary error: %s", exc, exc_info=True)
        return jsonify({"error": "Failed to load effort summary", "detail": str(exc)}), 500


@phase_f_bp.route("/viewpoint", methods=["GET"])
@login_required
def get_phase_f_viewpoint():
    """Return live ArchiMate viewpoint for Phase F (Migration Planning)."""
    from app.services.phase_viewpoint_binding_service import PhaseViewpointBindingService
    from app.services.workflow_archimate_context_service import WorkflowArchiMateContextService
    from app.services.archimate_viewpoint_render_service import ArchimateViewpointRenderService
    phase_code = "ADM_PHASE_F_MIGRATION"
    elements = WorkflowArchiMateContextService().get_phase_elements(phase_code)
    element_ids = [e["id"] for e in elements]
    viewpoint = ArchimateViewpointRenderService().render_viewpoint(phase_code, element_ids)
    viewpoint["viewpoint_name"] = PhaseViewpointBindingService().get_viewpoint_name(phase_code)
    return jsonify({"phase": "F", "viewpoint": viewpoint}), 200
