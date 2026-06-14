"""
DEPRECATED: This file is migrated to app/modules/architecture/.
Registration is now centralized via app.modules.architecture.register().
Do NOT modify -- kept as fallback until Phase 6 cleanup.

Architect Enhancement UI Routes

Provides view routes (HTML pages) for the architect enhancement features.
These routes render templates that interface with the respective API endpoints.

Pages:
- /solution-composer/ - Solution Composer Canvas
- /roadmap-builder/ - Roadmap Builder with dependencies
- /architecture-monitoring/ - Architecture Monitoring Dashboard
- /architecture-assistant/ - AI Architecture Assistant
- /market-intelligence/ - Market Intelligence Dashboard
"""

import logging

from flask import Blueprint, Response, current_app, flash, jsonify, redirect, render_template, request, url_for  # noqa: F401
from flask_login import login_required

from app import db
# ArchiMateHealthService import removed — architecture_health route deleted

architect_ui_bp = Blueprint("architect_ui", __name__)
logger = logging.getLogger(__name__)


def _check_llm_available() -> bool:
    """Return True if a valid LLM API key is configured, False otherwise."""
    try:
        cfg = current_app.config
        return bool(
            cfg.get("OPENAI_API_KEY") or cfg.get("LLM_API_KEY")
        )
    except Exception:
        return False


def _has_aligned_traceability_rows(matrix) -> bool:
    matrix = _normalize_traceability_matrix(matrix)
    return any(
        row.get("strategy") or row.get("business") or row.get("technology")
        for row in (matrix or [])
    )


def _normalize_traceability_matrix(matrix):
    if isinstance(matrix, dict):
        return matrix.get("rows", [])
    return matrix or []


def _build_solution_traceability_fallback_matrix(limit=50):
    """Build traceability rows from canonical solution relationships when ArchiMate links are thin."""
    from app.models.apqc_process import APQCProcess
    from app.models.archimate_core import ArchiMateElement
    from app.models.solution_models import Solution, SolutionArchiMateElement
    from app.models.solution_sad_models import SolutionAPQCProcess
    from app.models.vendor.vendor_organization import VendorProduct
    from app.modules.solutions_strategic.v2.routes.solution_design_routes import (
        _get_solution_applications,
        _get_solution_capabilities_payload,
    )

    rows_by_app = {}
    svp_table = db.metadata.tables.get("solution_vendor_products")
    solutions = (
        Solution.query.order_by(Solution.updated_at.desc(), Solution.id.desc()).limit(200).all()
    )

    def _merge_entities(target, items):
        seen = {(item.get("id"), item.get("name")) for item in target}
        for item in items:
            key = (item.get("id"), item.get("name"))
            if key not in seen:
                target.append(item)
                seen.add(key)

    for solution in solutions:
        try:
            applications = _get_solution_applications(solution.id)
            if not applications:
                continue

            strategy_items = [
                {
                    "id": capability.get("capability_id") or capability.get("id"),
                    "name": capability.get("name") or capability.get("capability_name"),
                    "type": "Capability",
                }
                for capability in _get_solution_capabilities_payload(solution)
                if capability.get("name") or capability.get("capability_name")
            ]

            process_links = SolutionAPQCProcess.query.filter_by(solution_id=solution.id).all()
            process_ids = [link.apqc_process_id for link in process_links if link.apqc_process_id]
            process_items = []
            if process_ids:
                process_items = [
                    {"id": process.id, "name": process.process_name, "type": "BusinessProcess"}
                    for process in APQCProcess.query.filter(APQCProcess.id.in_(process_ids)).all()
                ]

            technology_items = []
            tech_links = SolutionArchiMateElement.query.filter_by(solution_id=solution.id).all()
            tech_ids = [
                link.element_id
                for link in tech_links
                if (link.layer_type or "").lower() == "technology" and link.element_id
            ]
            if tech_ids:
                technology_items.extend(
                    {
                        "id": element.id,
                        "name": element.name,
                        "type": element.type or "Technology",
                    }
                    for element in ArchiMateElement.query.filter(
                        ArchiMateElement.id.in_(tech_ids)
                    ).all()
                )

            if not technology_items and svp_table is not None:
                vp_rows = db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
                    svp_table.select().where(svp_table.c.solution_id == solution.id)
                ).fetchall()
                vp_ids = [row.vendor_product_id for row in vp_rows if row.vendor_product_id]
                if vp_ids:
                    technology_items.extend(
                        {
                            "id": product.id,
                            "name": product.name,
                            "type": "VendorProduct",
                        }
                        for product in VendorProduct.query.filter(
                            VendorProduct.id.in_(vp_ids)
                        ).all()
                    )

            for application in applications:
                row = rows_by_app.setdefault(
                    application.id,
                    {
                        "application": {
                            "id": application.id,
                            "name": application.name,
                            "type": getattr(application, "component_type", None)
                            or "ApplicationComponent",
                        },
                        "strategy": [],
                        "business": [],
                        "technology": [],
                    },
                )
                _merge_entities(row["strategy"], strategy_items[:3])
                _merge_entities(row["business"], process_items[:3])
                _merge_entities(row["technology"], technology_items[:3])
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Solution traceability fallback failed for solution %s: %s",
                solution.id,
                exc,
            )
            try:
                db.session.rollback()
            except Exception:
                logger.debug("Failed to rollback session after solution traceability fallback error", exc_info=True)

    rows = list(rows_by_app.values())
    return rows[:limit] if limit is not None else rows


# NOTE: /solution-composer/ route migrated to solution_design_bp (/solutions/composer/).
# Old URL handled by legacy_redirects_bp.


# =============================================================================
# Roadmap Builder UI
# =============================================================================


@architect_ui_bp.route("/roadmap-builder/")
@login_required
def roadmap_builder():
    """Redirect to Enterprise Roadmap (capability-roadmap). Roadmap Builder is retired."""
    return redirect(url_for("main.capability_roadmap"))


# =============================================================================
# Architecture Monitoring + Health (removed — empty shell pages)
# =============================================================================

# architecture_monitoring, architecture_health, architecture_health_summary removed
# (3 routes — templates deleted, sidebar links removed)


# =============================================================================
# Architecture Assistant UI
# =============================================================================


@architect_ui_bp.route("/architecture-assistant/")
@login_required
def architecture_assistant():
    """
    AI Architecture Assistant page.
    Autonomous solution design with ARB submission draft generation.
    """
    return render_template("architecture_assistant/index.html", llm_available=_check_llm_available())


@architect_ui_bp.route("/architecture-assistant/solution/<int:solution_id>")
@login_required
def architecture_assistant_solution(solution_id):
    """
    AI Architecture Assistant page pre-loaded with an existing solution context.
    Allows continuing design or regenerating ARB for the given solution.
    """
    return render_template(
        "architecture_assistant/index.html",
        solution_id=solution_id,
        llm_available=_check_llm_available(),
    )


@architect_ui_bp.route("/architecture-assistant/model-viewer")
@login_required
def architecture_assistant_model_viewer():
    """
    Display ArchiMate Model Viewer page.

    Interactive visualization of generated ArchiMate 3.2 models.
    """
    return render_template("architecture_assistant/archimate_model_viewer.html")


# =============================================================================
# Market Intelligence UI
# =============================================================================


@architect_ui_bp.route("/market-intelligence/")
@login_required
def market_intelligence():
    """
    Market Intelligence Dashboard.
    Vendor risk monitoring, market trends, and alternative suggestions.
    """
    return render_template("market_intelligence/index.html")


# =============================================================================
# ArchiMate OEF Import / Export
# =============================================================================


@architect_ui_bp.route("/architecture/export/oef")
@login_required
def export_oef():
    """Export all ArchiMate elements as OEF XML download."""
    from app.services.archimate_oef_service import ArchiMateOEFService

    service = ArchiMateOEFService()
    xml_str = service.export_model()
    return Response(
        xml_str,
        mimetype="application/xml",
        headers={"Content-Disposition": "attachment; filename=archimate-model.xml"},
    )


@architect_ui_bp.route("/architecture/import/oef", methods=["GET", "POST"])
@login_required
def import_oef():
    """Import OEF XML file using ArchiMateExchangeService (deduplication-aware)."""
    from app.modules.architecture.services.archimate_exchange_service import (
        get_archimate_exchange_service,
    )

    if request.method == "GET":
        return render_template("archimate_crud/import_oef.html")

    file = request.files.get("oef_file")
    if not file:
        flash("No file uploaded", "error")
        return redirect(request.url)

    xml_content = file.read().decode("utf-8")
    service = get_archimate_exchange_service()
    result = service.import_archimate_xml(xml_content, current_user.id)
    return render_template("archimate_crud/import_oef.html", result=result)


# =============================================================================
# New Element Redirect Helper
# =============================================================================


@architect_ui_bp.route("/architecture/elements/new", methods=["GET"])
@login_required
def new_archimate_element():
    """Redirect to archimate_crud create page with pre-filled layer/type params."""
    element_type = request.args.get("type", "")
    layer = request.args.get("layer", "")
    return redirect(url_for("archimate_crud.create_element", layer=layer.lower(), element_type=element_type))


# =============================================================================
# Feature 1: Motivation View (Stakeholder Concern Mapping)
# =============================================================================


@architect_ui_bp.route("/architecture/motivation")
@login_required
def motivation_view():
    """Redirect to dashboard — Motivation swim-lane is now a dashboard view mode."""
    return redirect(url_for("archimate_crud.dashboard", layer="motivation"), code=302)


# =============================================================================
# Feature 2: Value Stream Mapping
# =============================================================================


@architect_ui_bp.route("/architecture/value-streams")
@login_required
def value_streams():
    """Redirect to dashboard — Strategy cards are now a dashboard view mode."""
    return redirect(url_for("archimate_crud.dashboard", layer="strategy"), code=302)


# =============================================================================
# Feature 3: Technology Lifecycle Dashboard
# =============================================================================


@architect_ui_bp.route("/architecture/technology-lifecycle")
@login_required
def technology_lifecycle():
    """Redirect to dashboard — Lifecycle columns are now a dashboard view mode."""
    return redirect(url_for("archimate_crud.dashboard", layer="technology"), code=302)


@architect_ui_bp.route("/api/archimate/elements/<int:element_id>/lifecycle", methods=["PATCH"])
@login_required
def update_lifecycle(element_id):
    """Update the lifecycle phase of a Technology element."""
    import json as _json

    from app.models.archimate_core import ArchiMateElement

    element = ArchiMateElement.query.get_or_404(element_id)
    phase = request.json.get("lifecycle")
    props = element.properties or {}
    if isinstance(props, str):
        try:
            props = _json.loads(props)
        except Exception:
            props = {}
    props["lifecycle"] = phase
    element.properties = _json.dumps(props)
    db.session.commit()
    return jsonify({"success": True})


# =============================================================================
# Cross-Layer Traceability Matrix [ARCH-016]
# =============================================================================


@architect_ui_bp.route("/architecture/traceability")
@login_required
def traceability_matrix():
    """Cross-layer traceability matrix across Strategy/Business/Application/Technology."""
    from app.services.archimate_traceability_service import ArchiMateTraceabilityService, get_gap_analysis

    service = ArchiMateTraceabilityService()
    direction = request.args.get('direction', 'forward')
    pivot_type = request.args.get('pivot_type', 'ApplicationComponent')
    plateau = request.args.get('plateau') or None
    search = request.args.get('search', '').strip() or None
    scope = request.args.get('scope', '').strip() or None
    page_size = 50
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    offset = (page - 1) * page_size
    pivot_layer = None
    if direction == 'inverse':
        pivot_type = 'Node'
        pivot_layer = 'Technology'
    pivot_types = service.get_available_pivot_types()
    total_count = service.count_matrix_rows(pivot_type=pivot_type, pivot_layer=pivot_layer,
                                            plateau=plateau, search=search, scope=scope)
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    matrix = _normalize_traceability_matrix(
        service.get_full_matrix(pivot_type=pivot_type, pivot_layer=pivot_layer, plateau=plateau,
                                limit=page_size, offset=offset, search=search, scope=scope)
    )
    gap_analysis = get_gap_analysis()
    if direction == 'forward' and pivot_type == "ApplicationComponent" and not plateau and not search and page == 1 and (
        not matrix or not _has_aligned_traceability_rows(matrix)
    ):
        fallback_matrix = _build_solution_traceability_fallback_matrix(limit=50)
        if fallback_matrix:
            matrix = fallback_matrix
    return render_template(
        "archimate_views/traceability.html",
        matrix=matrix,
        gap_analysis=gap_analysis,
        pivot_types=pivot_types,
        current_pivot_type=pivot_type,
        current_plateau=plateau,
        direction=direction,
        current_page=page,
        total_pages=total_pages,
        total_count=total_count,
        page_size=page_size,
        current_search=search or '',
        current_scope=scope or '',
    )


@architect_ui_bp.route("/api/archimate/traceability/export")
@login_required
def export_traceability_csv():
    """Export full traceability matrix as CSV download (no row limit)."""
    import csv
    import io

    from app.services.archimate_traceability_service import ArchiMateTraceabilityService

    service = ArchiMateTraceabilityService()
    pivot_type = request.args.get('pivot_type', 'ApplicationComponent')
    matrix = _normalize_traceability_matrix(service.get_full_matrix(pivot_type=pivot_type, limit=None))
    if pivot_type == "ApplicationComponent" and (not matrix or not _has_aligned_traceability_rows(matrix)):
        fallback_matrix = _build_solution_traceability_fallback_matrix(limit=None)
        if fallback_matrix:
            matrix = fallback_matrix

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Application Component', 'Type',
        'Strategy Elements', 'Business Elements',
        'Technology Elements', 'Data Objects'
    ])
    for row in matrix:
        strategy_names = ' | '.join(e['name'] for e in row.get('strategy', []))
        business_names = ' | '.join(e['name'] for e in row.get('business', []))
        tech_names = ' | '.join(e['name'] for e in row.get('technology', []))
        data_names = ' | '.join(e['name'] for e in row.get('data', []))
        writer.writerow([
            row['application']['name'],
            row['application'].get('type', pivot_type),
            strategy_names,
            business_names,
            tech_names,
            data_names,
        ])

    csv_string = output.getvalue()
    return Response(
        csv_string,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=archimate_traceability.csv'},
    )


@architect_ui_bp.route("/architecture/traceability/<int:element_id>")
@login_required
def element_traceability(element_id):
    """Single-element traceability chain view."""
    from app.services.archimate_impact_service import ArchiMateImpactService
    from app.services.archimate_traceability_service import ArchiMateTraceabilityService
    from app.models.archimate_core import ArchiMateElement

    service = ArchiMateTraceabilityService()
    impact_service = ArchiMateImpactService()
    element = ArchiMateElement.query.get_or_404(element_id)
    chain = service.get_element_chain(element_id)
    impact_summary = impact_service.get_impact_summary(element_id)
    return render_template(
        "archimate_views/element_traceability.html",
        element=element,
        chain=chain,
        impact_summary=impact_summary,
    )


@architect_ui_bp.route("/api/archimate/traceability/<int:element_id>")
@login_required
def api_element_traceability(element_id):
    """JSON traceability chain for a single element."""
    from app.services.archimate_traceability_service import ArchiMateTraceabilityService

    service = ArchiMateTraceabilityService()
    chain = service.get_element_chain(element_id)
    return jsonify(chain)


# =============================================================================
# Impact Analysis (ARCH-016)
# =============================================================================


@architect_ui_bp.route("/architecture/impact/<int:element_id>")
@login_required
def impact_analysis(element_id):
    """Impact Analysis page — change propagation for an ArchiMate element."""
    from app.services.archimate_impact_service import ArchiMateImpactService
    from app.models.archimate_core import ArchiMateElement

    service = ArchiMateImpactService()
    element = ArchiMateElement.query.get_or_404(element_id)
    analysis = service.analyze_impact(element_id)
    capability_gaps = service.get_capability_gaps(element_id)
    return render_template(
        "archimate_views/impact_analysis.html",
        element=element,
        analysis=analysis,
        capability_gaps=capability_gaps,
    )


@architect_ui_bp.route("/api/archimate/impact/<int:element_id>")
@login_required
def api_impact_analysis(element_id):
    """JSON impact analysis for an ArchiMate element."""
    from app.services.archimate_impact_service import ArchiMateImpactService

    service = ArchiMateImpactService()
    return jsonify(service.analyze_impact(element_id))


# =============================================================================
# Viewpoint API (ARCH-016)
# =============================================================================


@architect_ui_bp.route("/api/archimate/viewpoints")
@login_required
def list_viewpoints():
    """Return all 14 standard ArchiMate 3.2 role-based viewpoints."""
    from app.services.archimate_viewpoint_service import ArchiMateViewpointService

    service = ArchiMateViewpointService()
    vps = service.get_viewpoints()
    return jsonify(
        {
            k: {
                "name": v["name"],
                "description": v.get("description", ""),
                "roles": v["roles"],
                "layers": v.get("layers", []),
                "element_types": v.get("element_types", []),
            }
            for k, v in vps.items()
        }
    )


@architect_ui_bp.route("/api/archimate/viewpoints/<viewpoint_key>/elements")
@login_required
def elements_by_viewpoint(viewpoint_key):
    """Return ArchiMate elements filtered by the selected viewpoint."""
    from app.services.archimate_viewpoint_service import ArchiMateViewpointService
    from app.models.archimate_core import ArchiMateElement

    service = ArchiMateViewpointService()
    vp = service.get_viewpoint(viewpoint_key)
    query = ArchiMateElement.query
    if vp.get("layers"):
        lower_layers = [l.lower() for l in vp["layers"]]
        query = query.filter(db.func.lower(ArchiMateElement.layer).in_(lower_layers))
    if vp.get("element_types"):
        query = query.filter(ArchiMateElement.type.in_(vp["element_types"]))
    elements = query.limit(200).all()
    return jsonify(
        [
            {
                "id": e.id,
                "name": e.name,
                "layer": e.layer,
                "element_type": e.type,
            }
            for e in elements
        ]
    )


@architect_ui_bp.route("/api/archimate/viewpoints/<viewpoint_key>/diagram")
@login_required
def viewpoint_diagram_data(viewpoint_key):
    """Return elements + relationships for a viewpoint, formatted for ComposerRenderer.

    Used by platform-wide pages (Architecture Elements, Capability Map, Applications, Dashboard)
    to render inline viewpoint diagrams.

    Query params:
        limit: max elements (default 30, max 100)
        layer: optional extra layer filter
    """
    from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
    from app.modules.architecture.services.archimate_viewpoint_service import (
        ArchiMateViewpointService,
    )

    vp_service = ArchiMateViewpointService()
    vp_def = vp_service.get_viewpoint_definition(viewpoint_key)
    if not vp_def:
        return jsonify({"success": False, "error": f"Unknown viewpoint: {viewpoint_key}"}), 400

    allowed_types = vp_def.get("element_types")
    allowed_rel_types = vp_def.get("relationship_types")
    max_elements = min(int(request.args.get("limit", 30)), 100)
    extra_layer = request.args.get("layer")

    query = ArchiMateElement.query
    if allowed_types:
        query = query.filter(ArchiMateElement.type.in_(allowed_types))
    if extra_layer:
        query = query.filter(db.func.lower(ArchiMateElement.layer) == extra_layer.lower())
    elements = query.limit(max_elements).all()

    element_ids = {e.id for e in elements}

    rel_query = ArchiMateRelationship.query.filter(
        ArchiMateRelationship.source_id.in_(element_ids),
        ArchiMateRelationship.target_id.in_(element_ids),
    )
    if allowed_rel_types:
        rel_query = rel_query.filter(ArchiMateRelationship.type.in_(allowed_rel_types))
    relationships = rel_query.all()

    return jsonify({
        "success": True,
        "viewpoint": viewpoint_key,
        "viewpoint_name": vp_def["name"],
        "elements": [
            {"id": e.id, "name": e.name, "type": e.type or "ApplicationComponent",
             "layer": (e.layer or "application").lower()}
            for e in elements
        ],
        "relationships": [
            {"id": r.id, "source_id": r.source_id, "target_id": r.target_id,
             "type": r.type or "Association"}
            for r in relationships
        ],
        "count": len(elements),
        "relationship_count": len(relationships),
    })
