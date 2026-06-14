"""
UNIFIED ENTERPRISE ARCHITECTURE BLUEPRINT
Consolidates all architecture-related routes into a single comprehensive blueprint
following the Option 1 Full Consolidation strategy.

URL Structure:
/enterprise/* - Enterprise Architecture
/enterprise/data/* - Data Architecture
/enterprise/solutions/* - Solutions Architecture
/enterprise/software/* - Software Architecture
/enterprise/strategic/* - Strategic Planning
/enterprise/implementation/* - Implementation Planning
"""

import logging
from datetime import datetime  # dead-code-ok

from flask import (
    Blueprint,
    current_app,  # dead-code-ok
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required  # dead-code-ok
from sqlalchemy import func, or_, select, text  # dead-code-ok
from sqlalchemy.exc import IntegrityError as SQLIntegrityError  # dead-code-ok
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload  # dead-code-ok

from .. import db
from ..security.audit import audit_logger, AuditEventType, AuditEventSeverity
from ..exceptions import (  # dead-code-ok
    BusinessRuleError,
    DatabaseError,
    IntegrityError,
    NotFoundError,
    ValidationError,
)
from ..utils.api_helpers import api_error
from ..models import (  # dead-code-ok
    ConceptualDataModel,
    Contract,
    DataLineage,
    DataTransformation,
    DesignPattern,
    LogicalDataModel,
    PhysicalDataModel,
    SoftwareDependency,
    SoftwareModule,
    Solution,
    SolutionPattern,
)
from ..models.business_capabilities import (  # dead-code-ok
    BusinessCapability,
    BusinessFunction,
    Capability,
)
from ..models.archimate_core import ArchiMateElement
from ..models.implementation_migration import Gap
from ..models.implementation_migration import Plateau
from ..models.implementation_migration import WorkPackage
from ..models.metrics import ApplicationMetricsSnapshot  # dead-code-ok

logger = logging.getLogger(__name__)

# Create unified enterprise architecture blueprint
enterprise_bp = Blueprint("enterprise", __name__, url_prefix="/enterprise")

# ============================================================================
# DATA ARCHITECTURE ROUTES
# ============================================================================


@enterprise_bp.route("/data_architecture_dashboard")
@login_required
def data_architecture_dashboard():
    """Data Architecture Dashboard"""
    try:
        # Get metrics
        conceptual_count = ConceptualDataModel.query.count()
        logical_count = LogicalDataModel.query.count()
        physical_count = PhysicalDataModel.query.count()

        return render_template(
            "enterprise/data_architecture_dashboard.html",
            conceptual_count=conceptual_count,
            logical_count=logical_count,
            physical_count=physical_count,
        )
    except SQLAlchemyError as e:
        current_app.logger.error(
            f"Database error loading data architecture dashboard: {e}"
        )
        raise DatabaseError(
            message=f"Failed to load dashboard data: {str(e)}",
            user_message="Unable to load the data architecture dashboard. Please try again.",
            recovery_action="Refresh the page. If the problem persists, contact support.",
        )


@enterprise_bp.route("/data/models")
@login_required
def data_models():
    """Data Models Overview - renders existing data architecture dashboard"""
    try:
        conceptual_models = ConceptualDataModel.query.limit(500).all()
        logical_models = LogicalDataModel.query.limit(500).all()
        physical_models = PhysicalDataModel.query.limit(500).all()

        return render_template(
            "enterprise/data_architecture_dashboard.html",
            conceptual_models=conceptual_models,
            logical_models=logical_models,
            physical_models=physical_models,
        )
    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error loading data models: {e}")
        raise DatabaseError(
            message=f"Failed to load data models: {str(e)}",
            user_message="Unable to load data models. Please try again.",
            recovery_action="Return to the dashboard and try again.",
        )


@enterprise_bp.route("/api/data-models")
@login_required
def api_data_models():
    """Get all data architecture models."""
    try:
        conceptual_models = ConceptualDataModel.query.limit(500).all()
        logical_models = LogicalDataModel.query.limit(500).all()
        physical_models = PhysicalDataModel.query.limit(500).all()

        return jsonify(
            {
                "conceptual_models": [
                    {
                        "id": m.id,
                        "name": m.name,
                        "description": m.description,
                        "business_domain": m.business_domain,
                        "scope": m.scope,
                        "created_at": m.created_at.isoformat()
                        if m.created_at
                        else None,
                    }
                    for m in conceptual_models
                ],
                "logical_models": [
                    {
                        "id": m.id,
                        "name": m.name,
                        "description": m.description,
                        "normalization_level": m.normalization_level,
                        "design_pattern": m.design_pattern,
                        "conceptual_model_id": m.conceptual_model_id,
                        "created_at": m.created_at.isoformat()
                        if m.created_at
                        else None,
                    }
                    for m in logical_models
                ],
                "physical_models": [
                    {
                        "id": m.id,
                        "name": m.name,
                        "description": m.description,
                        "database_type": m.database_type,
                        "deployment_environment": m.deployment_environment,
                        "logical_model_id": m.logical_model_id,
                        "created_at": m.created_at.isoformat()
                        if m.created_at
                        else None,
                    }
                    for m in physical_models
                ],
            }
        )
    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error fetching data models: {e}")
        raise DatabaseError(
            message=f"Failed to fetch data models: {str(e)}",
            user_message="Unable to retrieve data models from the database.",
            recovery_action="Please try again. If the problem persists, contact support.",
        )


# ============================================================================
# SOLUTIONS ARCHITECTURE ROUTES
# ============================================================================


@enterprise_bp.route("/solutions_architecture_dashboard")
@login_required
def solutions_architecture_dashboard():
    """Solutions Architecture Dashboard"""
    try:
        solution_count = Solution.query.count()
        pattern_count = SolutionPattern.query.count()
        contract_count = Contract.query.count()

        return render_template(
            "enterprise/solutions_architecture_dashboard.html",
            solution_count=solution_count,
            pattern_count=pattern_count,
            contract_count=contract_count,
        )
    except SQLAlchemyError as e:
        current_app.logger.error(
            f"Database error loading solutions architecture dashboard: {e}"
        )
        raise DatabaseError(
            message=f"Failed to load solutions dashboard: {str(e)}",
            user_message="Unable to load the solutions architecture dashboard.",
            recovery_action="Refresh the page. If the problem persists, contact support.",
        )


@enterprise_bp.route("/api/solutions")
@login_required
def api_solutions():
    """Get all solutions architecture models."""
    try:
        solutions = Solution.query.limit(500).all()
        patterns = SolutionPattern.query.limit(500).all()
        contracts = Contract.query.limit(500).all()

        return jsonify(
            {
                "solutions": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "description": s.description,
                        "business_domain": s.business_domain,
                        "solution_type": s.solution_type,
                        "created_at": s.created_at.isoformat()
                        if s.created_at
                        else None,
                    }
                    for s in solutions
                ],
                "patterns": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "description": p.description,
                        "pattern_category": p.pattern_category,
                        "applicability": p.applicability,
                        "created_at": p.created_at.isoformat()
                        if p.created_at
                        else None,
                    }
                    for p in patterns
                ],
                "contracts": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "contract_type": c.contract_type,
                        "provider": c.provider,
                        "status": c.status,
                        "created_at": c.created_at.isoformat()
                        if c.created_at
                        else None,
                    }
                    for c in contracts
                ],
            }
        )
    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error fetching solutions: {e}")
        raise DatabaseError(
            message=f"Failed to fetch solutions data: {str(e)}",
            user_message="Unable to retrieve solutions from the database.",
            recovery_action="Please try again. If the problem persists, contact support.",
        )


# ============================================================================
# SOFTWARE ARCHITECTURE ROUTES
# ============================================================================


@enterprise_bp.route("/software_architecture_dashboard")
@login_required
def software_architecture_dashboard():
    """Software Architecture Dashboard"""
    try:
        component_count = ArchiMateElement.query.filter_by(
            type="ApplicationComponent", layer="Application"
        ).count()
        service_count = ArchiMateElement.query.filter_by(
            type="ApplicationService", layer="Application"
        ).count()
        interface_count = ArchiMateElement.query.filter_by(
            type="ApplicationInterface", layer="Application"
        ).count()
        dependency_count = SoftwareDependency.query.count()

        return render_template(
            "enterprise/software_architecture_dashboard.html",
            component_count=component_count,
            service_count=service_count,
            interface_count=interface_count,
            dependency_count=dependency_count,
        )
    except SQLAlchemyError as e:
        logger.error(
            f"Database error loading software architecture dashboard: {e}",
            exc_info=True,
        )
        raise DatabaseError(
            message=f"Failed to load software dashboard: {str(e)}",
            user_message="Unable to load the software architecture dashboard.",
            recovery_action="Refresh the page. If the problem persists, contact support.",
        )


@enterprise_bp.route("/api/software")
@login_required
def api_software():
    """Get all software architecture models."""
    try:
        modules = SoftwareModule.query.limit(500).all()
        patterns = DesignPattern.query.limit(500).all()
        dependencies = SoftwareDependency.query.limit(500).all()

        return jsonify(
            {
                "modules": [
                    {
                        "id": m.id,
                        "name": m.name,
                        "description": m.description,
                        "module_type": m.module_type,
                        "technology_stack": m.technology_stack,
                        "created_at": m.created_at.isoformat()
                        if m.created_at
                        else None,
                    }
                    for m in modules
                ],
                "patterns": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "description": p.description,
                        "pattern_language": p.pattern_language,
                        "complexity_level": p.complexity_level,
                        "created_at": p.created_at.isoformat()
                        if p.created_at
                        else None,
                    }
                    for p in patterns
                ],
                "dependencies": [
                    {
                        "id": d.id,
                        "source_module": d.source_module,
                        "target_module": d.target_module,
                        "dependency_type": d.dependency_type,
                        "strength": d.strength,
                        "created_at": d.created_at.isoformat()
                        if d.created_at
                        else None,
                    }
                    for d in dependencies
                ],
            }
        )
    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error fetching software models: {e}")
        raise DatabaseError(
            message=f"Failed to fetch software models: {str(e)}",
            user_message="Unable to retrieve software architecture models.",
            recovery_action="Please try again. If the problem persists, contact support.",
        )


# ============================================================================
# STRATEGIC PLANNING ROUTES
# ============================================================================


@enterprise_bp.route("/strategic")
@login_required
def strategic_planning_dashboard():
    """Strategic Planning Dashboard"""
    try:
        # Get strategic metrics with ArchiMate fallback for empty tables
        gap_count = Gap.query.count()
        if gap_count == 0:
            gap_count = ArchiMateElement.query.filter(
                ArchiMateElement.type.in_(["Gap", "GAP"])
            ).count()

        plateau_count = 0
        try:
            plateau_count = Plateau.query.count()
        except Exception as exc:
            logger.debug(f"Plateau query fallback: {exc}")
        if plateau_count == 0:
            plateau_count = ArchiMateElement.query.filter(
                ArchiMateElement.type.in_(["Plateau", "PLATEAU"])
            ).count()

        workpackage_count = 0
        try:
            workpackage_count = WorkPackage.query.count()
        except Exception as exc:
            logger.debug(f"WorkPackage query fallback: {exc}")
        if workpackage_count == 0:
            workpackage_count = ArchiMateElement.query.filter(
                ArchiMateElement.type.in_(["WorkPackage", "WORK_PACKAGE"])
            ).count()

        return render_template(
            "enterprise/strategic_planning_dashboard.html",
            gap_count=gap_count,
            plateau_count=plateau_count,
            workpackage_count=workpackage_count,
        )
    except SQLAlchemyError as e:
        logger.error(
            f"Database error loading strategic planning dashboard: {e}",
            exc_info=True,
        )
        raise DatabaseError(
            message=f"Failed to load strategic dashboard: {str(e)}",
            user_message="Unable to load the strategic planning dashboard.",
            recovery_action="Refresh the page. If the problem persists, contact support.",
        )


@enterprise_bp.route("/strategic/capability-health")
@login_required
def capability_health():
    """Capability Health Assessment — paginated to keep response times under 3 s."""
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)
        # Guard against absurdly large page sizes
        per_page = min(per_page, 200)

        pagination = BusinessCapability.query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        capabilities = pagination.items

        return render_template(
            "enterprise/capability_health.html",
            capabilities=capabilities,
            pagination=pagination,
        )
    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error loading capability health: {e}")
        raise DatabaseError(
            message=f"Failed to load capability health data: {str(e)}",
            user_message="Unable to load capability health assessment.",
            recovery_action="Return to the dashboard and try again.",
        )


@enterprise_bp.route("/strategic/investment-matrix")
@login_required
def investment_matrix():
    """Investment Matrix"""
    try:
        capabilities = BusinessCapability.query.limit(500).all()
        return render_template(
            "enterprise/investment_matrix.html", capabilities=capabilities
        )
    except Exception as e:
        current_app.logger.error(f"Error loading investment matrix: {e}")
        flash("Error loading investment matrix", "error")
        return redirect(url_for("enterprise.strategic_planning_dashboard"))


@enterprise_bp.route("/strategic/risk-assessment")
@login_required
def risk_assessment():
    """Risk Assessment"""
    try:
        gaps = Gap.query.limit(500).all()

        return render_template("enterprise/risk_assessment.html", gaps=gaps)
    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error loading risk assessment: {e}")
        raise DatabaseError(
            message=f"Failed to load risk assessment: {str(e)}",
            user_message="Unable to load risk assessment data.",
            recovery_action="Return to the dashboard and try again.",
        )


@enterprise_bp.route("/strategic/technology-roadmap")
@login_required
def technology_roadmap():
    """Technology Roadmap"""
    try:
        workpackages = WorkPackage.query.limit(500).all()

        return render_template(
            "enterprise/technology_roadmap.html", workpackages=workpackages
        )
    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error loading technology roadmap: {e}")
        raise DatabaseError(
            message=f"Failed to load technology roadmap: {str(e)}",
            user_message="Unable to load technology roadmap.",
            recovery_action="Return to the dashboard and try again.",
        )


# ============================================================================
# IMPLEMENTATION PLANNING ROUTES
# ============================================================================


# implementation_planning_dashboard removed — empty shell page, frozen sidebar link


@enterprise_bp.route("/implementation/work-packages")
@login_required
def work_packages():
    """Work Packages Management"""
    return render_template("enterprise/work_packages.html", workpackages=[])


@enterprise_bp.route("/api/work-packages", methods=["GET"])
@login_required
def api_list_work_packages():
    """Paginated work packages API."""
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 25, type=int), 100)
    search = request.args.get("q") or request.args.get("search", "")
    status_filter = request.args.get("status", "")
    sort_by = request.args.get("sort", "created_at")
    sort_dir = request.args.get("dir", "desc")

    ALLOWED_SORT = {"id", "name", "status", "priority", "target_date", "created_at", "percent_complete"}
    if sort_by not in ALLOWED_SORT:
        sort_by = "created_at"

    q = WorkPackage.query
    if search:
        q = q.filter(or_(
            WorkPackage.name.ilike(f"%{search}%"),
            WorkPackage.summary.ilike(f"%{search}%"),
        ))
    if status_filter:
        q = q.filter(WorkPackage.status == status_filter)

    sort_col = getattr(WorkPackage, sort_by, WorkPackage.created_at)
    q = q.order_by(sort_col.asc() if sort_dir == "asc" else sort_col.desc())

    paginated = q.paginate(page=page, per_page=per_page, error_out=False)
    offset = (page - 1) * per_page

    items = []
    for idx, wp in enumerate(paginated.items):
        items.append({
            "id": wp.id,
            "row_number": offset + idx + 1,
            "name": wp.name or "",
            "summary": wp.summary or wp.description or "",
            "status": wp.status or "Planned",
            "priority": wp.priority or "Normal",
            "percent_complete": wp.percent_complete or 0,
            "target_date": str(wp.target_date) if wp.target_date else None,
            "togaf_phase": wp.togaf_phase or "",
            "created_at": str(wp.created_at) if wp.created_at else None,
        })

    return jsonify({
        "work_packages": items,
        "total": paginated.total,
        "page": page,
        "pages": paginated.pages,
        "per_page": per_page,
    })


# CSRF: Protected via X-CSRFToken header sent by Platform.fetch
@enterprise_bp.route("/api/work-packages", methods=["POST"])
@login_required
def api_create_work_package():
    """Create a new work package. PROD-008"""
    data = request.get_json(force=True) or {}

    if not data.get("name", "").strip():
        return api_error("name is required", "MISSING_NAME")

    wp = WorkPackage(
        name=data["name"].strip(),
        summary=data.get("summary", ""),
        description=data.get("description", ""),
        status=data.get("status", "planned"),
        priority=data.get("priority", "medium"),
        togaf_phase=data.get("togaf_phase"),
        start_date=data.get("start_date"),
        target_date=data.get("target_date"),
        estimated_effort_hours=data.get("estimated_effort_hours"),
        estimated_cost=data.get("estimated_cost"),
        percent_complete=data.get("percent_complete", 0),
        plateau_id=data.get("plateau_id"),
        architecture_id=data.get("architecture_id"),
        owner_id=data.get("owner_id"),
        level=data.get("level", 1),
        color=data.get("color"),
    )
    db.session.add(wp)
    db.session.commit()
    try:
        audit_logger.log_event(
            AuditEventType.DATA_MODIFICATION,
            AuditEventSeverity.MEDIUM,
            "create",
            resource_type="work_package",
            resource_id=str(wp.id),
            details={"name": wp.name, "status": wp.status,
                     "user_id": current_user.id if current_user.is_authenticated else None},
            compliance_flags=["SOC2"],
        )
    except Exception as _exc:
        logger.warning("audit log failed for api_create_work_package: %s", _exc)
    return jsonify({"status": "created", "id": wp.id}), 201


# CSRF: Protected via X-CSRFToken header sent by Platform.fetch
@enterprise_bp.route("/api/work-packages/<int:wp_id>", methods=["PATCH"])
@login_required
def api_update_work_package(wp_id):
    """Update a work package. PROD-008"""
    wp = WorkPackage.query.get_or_404(wp_id)
    data = request.get_json(force=True) or {}

    allowed = {
        "name", "summary", "description", "status", "priority", "togaf_phase",
        "start_date", "target_date", "estimated_effort_hours", "actual_effort_hours",
        "estimated_cost", "actual_cost", "percent_complete", "plateau_id",
        "architecture_id", "owner_id", "level", "color", "sequence_order",
        "capability_id", "parent_id", "dependencies",
    }
    for field in allowed:
        if field in data:
            setattr(wp, field, data[field])

    db.session.commit()
    try:
        audit_logger.log_event(
            AuditEventType.DATA_MODIFICATION,
            AuditEventSeverity.MEDIUM,
            "update",
            resource_type="work_package",
            resource_id=str(wp_id),
            details={"name": wp.name, "status": wp.status,
                     "user_id": current_user.id if current_user.is_authenticated else None},
            compliance_flags=["SOC2"],
        )
    except Exception as _exc:
        logger.warning("audit log failed for api_update_work_package: %s", _exc)
    return jsonify({"status": "ok", "id": wp.id})


@enterprise_bp.route("/api/work-packages/bulk", methods=["DELETE"])
@login_required
def api_bulk_delete_work_packages():
    """Bulk delete work packages."""
    data = request.get_json() or {}
    ids = data.get("ids", [])
    if not ids or not isinstance(ids, list):
        return api_error("ids list required", "MISSING_IDS")
    wps = WorkPackage.query.filter(WorkPackage.id.in_(ids)).all()
    deleted = 0
    for wp in wps:
        wp_id = wp.id
        wp_name = wp.name
        db.session.delete(wp)
        db.session.flush()
        deleted += 1
        try:
            audit_logger.log_event(
                AuditEventType.DATA_MODIFICATION,
                AuditEventSeverity.HIGH,
                "delete",
                resource_type="work_package",
                resource_id=str(wp_id),
                details={"name": wp_name,
                         "user_id": current_user.id if current_user.is_authenticated else None},
                compliance_flags=["SOC2"],
            )
        except Exception as _exc:
            logger.warning("audit log failed for bulk_delete wp %s: %s", wp_id, _exc)
    db.session.commit()
    return jsonify({"deleted": deleted})


@enterprise_bp.route("/implementation/plateaus")
@login_required
def plateaus():
    """Implementation Plateaus"""
    try:
        plateaus = Plateau.query.limit(500).all()
        return render_template("enterprise/plateaus.html", plateaus=plateaus)
    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error loading plateaus: {e}")
        raise DatabaseError(
            message=f"Failed to load plateaus: {str(e)}",
            user_message="Unable to load implementation plateaus.",
            recovery_action="Return to the dashboard and try again.",
        )


@enterprise_bp.route("/implementation/gap-analysis")
@login_required
def gap_analysis():
    """Gap Analysis"""
    try:
        gaps = Gap.query.limit(500).all()

        return render_template("enterprise/gap_analysis.html", gaps=gaps)
    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error loading gap analysis: {e}")
        raise DatabaseError(
            message=f"Failed to load gap analysis: {str(e)}",
            user_message="Unable to load gap analysis.",
            recovery_action="Return to the dashboard and try again.",
        )


# ============================================================================
# ANALYSIS & AI TOOLS ROUTES
# ============================================================================


@enterprise_bp.route("/analysis/ai-architecture")
@login_required
def ai_architecture_analysis():
    """AI Architecture Analysis — displays architectural intelligence dashboard"""
    try:
        from app.models.ai_recommendations import AIRecommendation
        from app.models.implementation_migration import Gap
        from app.models.application_portfolio import ApplicationComponent
        from sqlalchemy import func

        # Fetch recent AI recommendations
        ai_recommendations = (
            AIRecommendation.query.order_by(AIRecommendation.created_at.desc())
            .limit(20)
            .all()
        )

        # Count gaps by severity
        gaps_by_severity = {
            "critical": Gap.query.filter_by(severity="critical").count(),
            "high": Gap.query.filter_by(severity="high").count(),
            "medium": Gap.query.filter_by(severity="medium").count(),
            "low": Gap.query.filter_by(severity="low").count(),
        }

        # Fetch applications needing review
        apps_needing_review = (
            ApplicationComponent.query.filter_by(lifecycle_status="under_review")
            .order_by(ApplicationComponent.name)
            .limit(10)
            .all()
        )

        # Total counts
        total_recommendations = AIRecommendation.query.count()
        total_gaps = Gap.query.count()

        return render_template(
            "enterprise/ai_architecture_analysis.html",
            ai_recommendations=ai_recommendations,
            gaps_by_severity=gaps_by_severity,
            apps_needing_review=apps_needing_review,
            total_recommendations=total_recommendations,
            total_gaps=total_gaps,
        )
    except Exception as e:
        current_app.logger.error(f"Error loading AI architecture analysis: {e}")
        raise DatabaseError(
            message=f"Failed to load AI architecture analysis: {str(e)}",
            user_message="Unable to load AI architecture analysis.",
            recovery_action="Return to the dashboard and try again.",
        )


# gap_discovery removed — empty shell page, frozen sidebar link


@enterprise_bp.route("/analysis/impact-analysis")
@login_required
def impact_analysis():
    """Impact Analysis — assess downstream impact of architecture changes"""
    try:
        from app.models.traceability import ImpactAnalysisResult
        from app.models.application_portfolio import ApplicationComponent
        from app.models.business_capabilities import BusinessCapability
        from sqlalchemy import func

        # Get filter parameters from query string
        selected_element_type = request.args.get(
            "element_type"
        )  # 'application' or 'capability'
        selected_element_id = request.args.get("element_id", type=int)

        # Fetch all applications and capabilities for dropdowns (id + name only)
        applications = (
            db.session.query(ApplicationComponent.id, ApplicationComponent.name)
            .order_by(ApplicationComponent.name)
            .all()
        )

        capabilities = (
            db.session.query(BusinessCapability.id, BusinessCapability.name)
            .order_by(BusinessCapability.name)
            .all()
        )

        # Fetch recent impact analyses (last 20)
        recent_analyses = (
            ImpactAnalysisResult.query.order_by(ImpactAnalysisResult.created_at.desc())
            .limit(20)
            .all()
        )

        # Filter analyses if element type and id provided
        filtered_analyses = None
        if selected_element_type and selected_element_id:
            filtered_analyses = (
                ImpactAnalysisResult.query.filter_by(
                    trigger_element_type=selected_element_type,
                    trigger_element_id=selected_element_id,
                )
                .order_by(ImpactAnalysisResult.created_at.desc())
                .all()
            )

        # Calculate summary metrics
        total_analyses = ImpactAnalysisResult.query.count()
        critical_count = ImpactAnalysisResult.query.filter_by(
            overall_severity="critical"
        ).count()
        high_count = ImpactAnalysisResult.query.filter_by(
            overall_severity="high"
        ).count()

        # Calculate average affected applications
        avg_result = db.session.query(
            func.avg(ImpactAnalysisResult.affected_applications_count)
        ).scalar()
        avg_affected_applications = round(avg_result, 1) if avg_result else 0

        return render_template(
            "enterprise/impact_analysis.html",
            recent_analyses=recent_analyses,
            applications=applications,
            capabilities=capabilities,
            selected_element_type=selected_element_type,
            selected_element_id=selected_element_id,
            filtered_analyses=filtered_analyses,
            total_analyses=total_analyses,
            critical_count=critical_count,
            high_count=high_count,
            avg_affected_applications=avg_affected_applications,
        )
    except Exception as e:
        current_app.logger.error(f"Error loading impact analysis: {e}")
        raise DatabaseError(
            message=f"Failed to load impact analysis: {str(e)}",
            user_message="Unable to load impact analysis.",
            recovery_action="Return to the dashboard and try again.",
        )


@enterprise_bp.route("/analysis/process-optimization")
@login_required
def process_optimization():
    """Process Optimization — identify automation and simplification opportunities"""
    try:
        from app.models.process_data import BusinessProcess
        from app.models.industry_apqc import IndustryProcessRecommendation
        from app.models.business_capabilities import BusinessCapability
        from sqlalchemy import func

        # Total process count
        total_processes = BusinessProcess.query.count()

        # Count processes by status
        processes_by_status = {}
        status_counts = (
            db.session.query(BusinessProcess.status, func.count(BusinessProcess.id))
            .group_by(BusinessProcess.status)
            .all()
        )

        for status, count in status_counts:
            if status:
                processes_by_status[status] = count

        # Average automation percentage
        avg_result = (
            db.session.query(func.avg(BusinessProcess.automation_percentage))
            .filter(BusinessProcess.automation_percentage.isnot(None))
            .scalar()
        )
        avg_automation = round(avg_result, 1) if avg_result else 0.0

        # Low automation processes (automation < 30%)
        low_automation_processes = (
            BusinessProcess.query.filter(BusinessProcess.automation_percentage < 30)
            .order_by(BusinessProcess.automation_percentage.asc())
            .limit(15)
            .all()
        )

        # Fetch optimization recommendations (last 20)
        optimization_recommendations = (
            IndustryProcessRecommendation.query.order_by(
                IndustryProcessRecommendation.created_at.desc()
            )
            .limit(20)
            .all()
        )

        # High complexity processes (those with many subprocesses)
        # Query for processes that have more than 3 child processes
        from sqlalchemy.orm import aliased

        Child = aliased(BusinessProcess)
        high_complexity_processes = (
            db.session.query(BusinessProcess)
            .join(
                Child,
                Child.parent_process_id == BusinessProcess.id,
                isouter=True,
            )
            .group_by(BusinessProcess.id)
            .having(func.count(Child.id) > 3)
            .all()
        )

        # Count low automation processes
        low_automation_count = BusinessProcess.query.filter(
            BusinessProcess.automation_percentage < 30
        ).count()

        # Count open recommendations
        open_recommendations_count = IndustryProcessRecommendation.query.filter_by(
            status="pending"
        ).count()

        return render_template(
            "enterprise/process_optimization.html",
            total_processes=total_processes,
            processes_by_status=processes_by_status,
            avg_automation=avg_automation,
            low_automation_processes=low_automation_processes,
            optimization_recommendations=optimization_recommendations,
            high_complexity_processes=high_complexity_processes,
            low_automation_count=low_automation_count,
            open_recommendations_count=open_recommendations_count,
        )
    except Exception as e:
        current_app.logger.error(f"Error loading process optimization: {e}")
        raise DatabaseError(
            message=f"Failed to load process optimization: {str(e)}",
            user_message="Unable to load process optimization tool.",
            recovery_action="Return to the dashboard and try again.",
        )


# ============================================================================
# MAIN ENTERPRISE DASHBOARD
# ============================================================================


@enterprise_bp.route("/")
@login_required
def enterprise_dashboard():
    """Main Enterprise Architecture Dashboard"""
    try:
        # Get overall metrics
        data_models_count = (
            ConceptualDataModel.query.count()
            + LogicalDataModel.query.count()
            + PhysicalDataModel.query.count()
        )
        solutions_count = Solution.query.count()
        software_modules_count = SoftwareModule.query.count()

        # Gaps with ArchiMate fallback for empty tables
        gaps_count = Gap.query.count()
        if gaps_count == 0:
            gaps_count = ArchiMateElement.query.filter(
                ArchiMateElement.type.in_(["Gap", "GAP"])
            ).count()

        return render_template(
            "enterprise/enterprise_dashboard.html",
            data_models_count=data_models_count,
            solutions_count=solutions_count,
            software_modules_count=software_modules_count,
            gaps_count=gaps_count,
        )
    except Exception as e:
        logger.error(f"Enterprise dashboard stats error: {e}", exc_info=True)
        flash("Error loading dashboard", "error")
        return render_template(
            "enterprise/enterprise_dashboard.html",
            data_models_count=0,
            solutions_count=0,
            software_modules_count=0,
            gaps_count=0,
        )
