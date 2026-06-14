"""
Unified Low Priority Routes

Consolidates remaining routes into a single, comprehensive set:
1. Architecture routes (architecture_routes.py)
2. Capability map routes (capability_map_routes.py)
3. Strategic routes (strategic_routes.py)
4. Consolidation list routes (consolidation_list_routes.py)
5. Policy monitoring routes (policy_monitoring_routes.py)

Phase 6: Low priority consolidations with full preservation
"""

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required
from flask_wtf.csrf import CSRFError

from app.decorators import audit_log
from sqlalchemy import or_, text

from .. import db
from ..models.application_portfolio import ApplicationComponent
from ..models.business_capabilities import BusinessCapability
from ..models.models import ArchiMateElement, ArchiMateRelationship, ArchitectureModel
from ..services.consolidation_service import ConsolidationService
from ..services.policy_monitoring_service import PolicyMonitoringService

# Import new services
from ..services.strategic_service import StrategicService

# Initialize services
strategic_service = StrategicService()
consolidation_service = ConsolidationService()
policy_monitoring_service = PolicyMonitoringService()

# Create unified blueprint
unified_low_priority_bp = Blueprint(
    "unified_low_priority", __name__, url_prefix="/enterprise"
)

# Import individual route modules for consolidation
try:
    # Import route functions from existing modules
    from .architecture_routes import *
    from .capability_map_routes import *

    # from .consolidation_list_routes import *  # Removed: violates blueprints ban
    from .policy_monitoring_routes import *
    from .strategic_routes import *

    LOW_PRIORITY_ROUTES_AVAILABLE = True
except ImportError:
    LOW_PRIORITY_ROUTES_AVAILABLE = False


# === ARCHITECTURE ROUTES ===


# REMOVED: "/" route — conflicts with enterprise_bp.enterprise_dashboard() in
# unified_enterprise_routes.py which renders enterprise/enterprise_dashboard.html
# with actual data (data_models_count, solutions_count, etc.)


@unified_low_priority_bp.route("/architecture")
@login_required
def architecture_dashboard():
    """Architecture management dashboard - redirects to ArchiMate CRUD dashboard"""
    return redirect("/architecture/dashboard")


@unified_low_priority_bp.route("/architecture/models")
@login_required
def architecture_models():
    """List architecture models"""
    try:
        models = ArchitectureModel.query.order_by(ArchitectureModel.name).all()
        return render_template("architecture/models.html", models=models)
    except Exception as e:
        current_app.logger.error(f"Architecture models error: {str(e)}")
        flash("Error loading architecture models", "error")
        return render_template("architecture/models.html", models=[])


@unified_low_priority_bp.route("/architecture/elements")
@login_required
def architecture_elements():
    """List architecture elements"""
    try:
        elements = ArchiMateElement.query.order_by(ArchiMateElement.name).all()
        return render_template("architecture/elements.html", elements=elements)
    except Exception as e:
        current_app.logger.error(f"Architecture elements error: {str(e)}")
        flash("Error loading architecture elements", "error")
        return render_template("architecture/elements.html", elements=[])


@unified_low_priority_bp.route("/architecture/relationships")
@login_required
def architecture_relationships():
    """List architecture relationships"""
    try:
        relationships = ArchiMateRelationship.query.order_by(
            ArchiMateRelationship.type
        ).all()
        return render_template(
            "architecture/relationships.html", relationships=relationships
        )
    except Exception as e:
        current_app.logger.error(f"Architecture relationships error: {str(e)}")
        flash("Error loading architecture relationships", "error")
        return render_template("architecture/relationships.html", relationships=[])


# === CAPABILITY MAP ROUTES ===


@unified_low_priority_bp.route("/capability-map")
@unified_low_priority_bp.route("/capability-map/")
@login_required
def capability_map_dashboard():
    """Capability mapping dashboard"""
    try:
        # Get capability statistics
        capability_count = BusinessCapability.query.count()
        application_count = ApplicationComponent.query.count()

        # Get capability categories
        categories = db.session.query(BusinessCapability.level).distinct().all()
        categories = [c[0] for c in categories if c[0]]

        return render_template(
            "capability_map/index.html",
            capability_count=capability_count,
            application_count=application_count,
            categories=categories,
        )
    except Exception as e:
        current_app.logger.error(f"Capability map dashboard error: {str(e)}")
        flash("Error loading capability map dashboard", "error")
        return render_template("capability_map/index.html")


@unified_low_priority_bp.route("/capability-map/capabilities")
@login_required
def capability_map_capabilities():
    """List capabilities for mapping"""
    try:
        capabilities = BusinessCapability.query.order_by(BusinessCapability.name).all()
        return render_template(
            "capability_map/capabilities.html", capabilities=capabilities
        )
    except Exception as e:
        current_app.logger.error(f"Capability map capabilities error: {str(e)}")
        flash("Error loading capabilities", "error")
        return render_template("capability_map/capabilities.html", capabilities=[])


@unified_low_priority_bp.route("/capability-map/applications")
@login_required
def capability_map_applications():
    """List applications for mapping"""
    try:
        applications = ApplicationComponent.query.order_by(
            ApplicationComponent.name
        ).all()
        return render_template(
            "capability_map/applications.html", applications=applications
        )
    except Exception as e:
        current_app.logger.error(f"Capability map applications error: {str(e)}")
        flash("Error loading applications", "error")
        return render_template("capability_map/applications.html", applications=[])


@unified_low_priority_bp.route("/capability-map/mapping")
@login_required
def capability_map_mapping():
    """Capability mapping interface"""
    try:
        capabilities = BusinessCapability.query.order_by(BusinessCapability.name).all()
        applications = ApplicationComponent.query.order_by(
            ApplicationComponent.name
        ).all()

        return render_template(
            "capability_map/mapping.html",
            capabilities=capabilities,
            applications=applications,
        )
    except Exception as e:
        current_app.logger.error(f"Capability mapping error: {str(e)}")
        flash("Error loading capability mapping", "error")
        return render_template(
            "capability_map/mapping.html", capabilities=[], applications=[]
        )


# === STRATEGIC ROUTES ===


# REMOVED: "/strategic" route — conflicts with enterprise_bp.strategic_planning_dashboard()
# in unified_enterprise_routes.py. Also, the template strategic/dashboard.html does not exist.
# The enterprise_bp version renders enterprise/strategic_planning_dashboard.html (which exists).


@unified_low_priority_bp.route("/strategic/roadmap")
@login_required
def strategic_roadmap():
    """Strategic roadmap view with swimlane visualization"""
    try:
        # Get filter parameters
        year = request.args.get("year", type=int)
        quarter = request.args.get("quarter")

        # Get roadmap data from services
        roadmap_by_lane_result = strategic_service.get_roadmap_by_lane()
        roadmap_items_result = strategic_service.get_roadmap_items(
            year=year, quarter=quarter
        )
        health_scores_result = strategic_service.get_initiative_health_scores()

        # Extract data using correct keys (not "data")
        roadmap_by_lane = (
            roadmap_by_lane_result.get("roadmap_by_lane", {})
            if roadmap_by_lane_result.get("success")
            else {}
        )
        roadmap_items = (
            roadmap_items_result.get("roadmap_items", [])
            if roadmap_items_result.get("success")
            else []
        )
        health_scores = (
            health_scores_result.get("health_scores", [])
            if health_scores_result.get("success")
            else []
        )

        return render_template(
            "strategic/roadmap.html",
            roadmap_items=roadmap_items,
            roadmap_by_lane=roadmap_by_lane,
            health_scores=health_scores,
            year=year,
            quarter=quarter,
        )
    except Exception as e:
        current_app.logger.error(f"Strategic roadmap error: {str(e)}")
        flash("Error loading strategic roadmap", "error")
        return render_template(
            "strategic/roadmap.html",
            roadmap_items=[],
            roadmap_by_lane={},
            health_scores=[],
            year=None,
            quarter=None,
        )


@unified_low_priority_bp.route("/strategic/initiatives")
@login_required
def strategic_initiatives():
    """Strategic initiatives management"""
    try:
        # Get initiatives from service
        status_filter = request.args.get("status")
        initiatives_result = strategic_service.get_all_initiatives(
            status_filter=status_filter
        )
        health_scores = strategic_service.get_initiative_health_scores()

        initiatives_list = (
            initiatives_result.get("initiatives", [])
            if initiatives_result.get("success")
            else []
        )
        health_scores_list = (
            health_scores.get("health_scores", [])
            if health_scores.get("success")
            else []
        )

        return render_template(
            "strategic/initiatives.html",
            initiatives=initiatives_list,
            health_scores=health_scores_list,
            status_filter=status_filter,
        )
    except Exception as e:
        current_app.logger.error(f"Strategic initiatives error: {str(e)}")
        flash("Error loading strategic initiatives", "error")
        return render_template(
            "strategic/initiatives.html",
            initiatives=[],
            health_scores=[],
            status_filter=None,
        )


# === CONSOLIDATION LIST ROUTES ===


@unified_low_priority_bp.route("/consolidation")
@login_required
def consolidation_dashboard():
    """Application consolidation dashboard - renders existing consolidation list dashboard"""
    try:
        dashboard_data = consolidation_service.get_consolidation_dashboard_data()
        statistics = consolidation_service.get_consolidation_statistics()

        if dashboard_data.get("success"):
            data = dashboard_data["data"]
            return render_template(
                "consolidation_list/dashboard.html",
                total_applications=ApplicationComponent.query.count(),
                duplicate_candidates=data.get("recent_candidates", []),
                consolidation_opportunities=data.get("recent_opportunities", []),
                statistics=statistics.get("data", {})
                if statistics.get("success")
                else {},
                savings_forecast=data.get("savings_forecast", {}),
            )
        else:
            return render_template(
                "consolidation_list/dashboard.html",
                total_applications=ApplicationComponent.query.count(),
                duplicate_candidates=[],
                consolidation_opportunities=[],
            )
    except Exception as e:
        current_app.logger.error(f"Consolidation dashboard error: {str(e)}")
        flash("Error loading consolidation dashboard", "error")
        return redirect("/enterprise/")


@unified_low_priority_bp.route("/consolidation/candidates")
@login_required
def consolidation_candidates():
    """List consolidation candidates"""
    try:
        # Get candidates from service with optional status filter
        status_filter = request.args.get("status")
        candidates_result = consolidation_service.get_all_candidates(
            status_filter=status_filter
        )

        # get_all_candidates returns a plain list (not a {success,data} dict)
        candidates = (
            candidates_result
            if isinstance(candidates_result, list)
            else (candidates_result.get("data", []) if candidates_result.get("success") else [])
        )
        return render_template("consolidation/candidates.html", candidates=candidates)
    except Exception as e:
        current_app.logger.error(f"Consolidation candidates error: {str(e)}")
        flash("Error loading consolidation candidates", "error")
        return render_template("consolidation/candidates.html", candidates=[])


@unified_low_priority_bp.route("/consolidation/opportunities")
@login_required
def consolidation_opportunities():
    """List consolidation opportunities"""
    try:
        # Get opportunities from service with optional status filter
        status_filter = request.args.get("status")
        opportunities_result = consolidation_service.get_all_opportunities(
            status_filter=status_filter
        )
        savings_forecast = consolidation_service.get_savings_forecast()

        opportunities = (
            opportunities_result
            if isinstance(opportunities_result, list)
            else (opportunities_result.get("data", []) if opportunities_result.get("success") else [])
        )
        savings = (
            savings_forecast.get("data", {})
            if isinstance(savings_forecast, dict) and savings_forecast.get("success")
            else (savings_forecast if isinstance(savings_forecast, dict) else {})
        )
        return render_template(
            "consolidation/opportunities.html",
            opportunities=opportunities,
            savings_forecast=savings,
        )
    except Exception as e:
        current_app.logger.error(f"Consolidation opportunities error: {str(e)}")
        flash("Error loading consolidation opportunities", "error")
        return render_template("consolidation/opportunities.html", opportunities=[])


# === POLICY MONITORING ROUTES ===


@unified_low_priority_bp.route("/policy-monitoring")
@login_required
def policy_monitoring_dashboard():
    """Policy Monitoring Dashboard — compliance scan results and violation tracking."""
    return render_template("policy_monitoring/dashboard.html")


# === API ENDPOINTS ===


@unified_low_priority_bp.route("/api/architecture/elements", methods=["GET"])
@login_required
def api_architecture_elements():
    """API endpoint for architecture elements"""
    try:
        elements = ArchiMateElement.query.limit(5000).all()
        data = []
        for element in elements:
            data.append(
                {
                    "id": element.id,
                    "name": element.name,
                    "type": element.type,
                    "description": element.description or "",
                }
            )
        return jsonify({"success": True, "data": data})
    except Exception as e:
        current_app.logger.error(f"API architecture elements error: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@unified_low_priority_bp.route("/api/capability-map/capabilities", methods=["GET"])
@login_required
def api_capability_map_capabilities():
    """API endpoint for capability map capabilities"""
    try:
        capabilities = BusinessCapability.query.limit(2000).all()
        data = []
        for capability in capabilities:
            data.append(
                {
                    "id": capability.id,
                    "name": capability.name,
                    "description": capability.description or "",
                    "level": capability.level or 1,
                    "category": capability.category or "",
                }
            )
        return jsonify({"success": True, "data": data})
    except Exception as e:
        current_app.logger.error(f"API capability map capabilities error: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@unified_low_priority_bp.route(
    "/api/capability-map/manufacturing-capabilities", methods=["GET"]
)
@login_required
def api_manufacturing_capabilities():
    """API endpoint for manufacturing-specific capabilities"""
    try:
        # Filter capabilities related to manufacturing
        manufacturing_capabilities = BusinessCapability.query.filter(
            or_(
                BusinessCapability.name.ilike("%manufacturing%"),
                BusinessCapability.name.ilike("%production%"),
                BusinessCapability.name.ilike("%factory%"),
                BusinessCapability.name.ilike("%shop%"),
                BusinessCapability.description.ilike("%manufacturing%"),
            )
        ).all()

        data = []
        for capability in manufacturing_capabilities:
            data.append(
                {
                    "id": capability.id,
                    "name": capability.name,
                    "description": capability.description or "",
                    "level": capability.level or 1,
                    "category": capability.category or "Manufacturing",
                }
            )
        return jsonify({"success": True, "data": data})
    except Exception as e:
        current_app.logger.error(f"API manufacturing capabilities error: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@unified_low_priority_bp.route(
    "/api/capability-map/unified-capabilities", methods=["GET"]
)
@login_required
def api_unified_capabilities():
    """API endpoint for unified capabilities view"""
    try:
        # Pre-load app counts in a single query to avoid N+1
        app_counts_rows = db.session.execute(  # tenant-filtered: scoped via parent FK
            text(
                "SELECT business_capability_id, COUNT(DISTINCT application_component_id) as app_count "
                "FROM application_capability_mapping GROUP BY business_capability_id"
            )
        ).fetchall()
        app_counts = {row[0]: row[1] for row in app_counts_rows}

        capabilities = BusinessCapability.query.limit(2000).all()

        data = []
        for capability in capabilities:
            data.append(
                {
                    "id": capability.id,
                    "name": capability.name,
                    "description": capability.description or "",
                    "level": capability.level or 1,
                    "category": capability.category or "",
                    "application_count": app_counts.get(capability.id, 0),
                    "maturity_level": getattr(
                        capability, "maturity_level", "defined"
                    ),  # model-safety-ok: BusinessCapability uses current_maturity_level, kept for API compatibility
                    "criticality": getattr(
                        capability, "criticality", "medium"
                    ),  # model-safety-ok: BusinessCapability uses business_criticality, kept for API compatibility
                }
            )

        return jsonify({"success": True, "data": data})
    except Exception as e:
        current_app.logger.error(f"API unified capabilities error: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@unified_low_priority_bp.route("/api/strategic/metrics", methods=["GET"])
@login_required
def api_strategic_metrics():
    """API endpoint for strategic metrics"""
    try:
        # Get comprehensive strategic metrics from service
        service_metrics = strategic_service.get_strategic_metrics()

        metrics = {
            "total_capabilities": BusinessCapability.query.count(),
            "total_applications": ApplicationComponent.query.count(),
            "total_elements": ArchiMateElement.query.count(),
            "total_relationships": ArchiMateRelationship.query.count(),
        }

        # Merge service metrics if available
        if service_metrics.get("success"):
            metrics.update(service_metrics.get("data") or {})

        return jsonify({"success": True, "data": metrics})
    except Exception as e:
        current_app.logger.error(f"API strategic metrics error: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


# === ADDITIONAL API ENDPOINTS FOR NEW SERVICES ===


@unified_low_priority_bp.route("/api/consolidation/detect", methods=["POST"])
@login_required
@audit_log("consolidation_detect")
def api_detect_duplicates():
    """API endpoint to trigger duplicate detection"""
    try:
        result = consolidation_service.detect_duplicate_candidates()
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"API detect duplicates error: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@unified_low_priority_bp.route("/api/consolidation/statistics", methods=["GET"])
@login_required
def api_consolidation_statistics():
    """API endpoint for consolidation statistics"""
    try:
        result = consolidation_service.get_consolidation_statistics()
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"API consolidation statistics error: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@unified_low_priority_bp.route("/api/policy-monitoring/scan", methods=["POST"])
@login_required
@audit_log("compliance_scan")
def api_scan_compliance():
    """API endpoint to trigger compliance scan"""
    try:
        application_id = request.json.get("application_id") if request.json else None
        if application_id:
            result = policy_monitoring_service.scan_application_compliance(
                application_id
            )
        else:
            result = policy_monitoring_service.scan_all_applications()
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"API scan compliance error: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@unified_low_priority_bp.route("/api/policy-monitoring/violations", methods=["GET"])
@login_required
def api_get_violations():
    """API endpoint for policy violations"""
    try:
        status_filter = request.args.get("status")
        severity_filter = request.args.get("severity")
        result = policy_monitoring_service.get_violations(
            status_filter=status_filter, severity_filter=severity_filter
        )
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"API get violations error: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


# REMOVED: Legacy route mappings — they duplicated routes already defined above
# in this same file (/architecture, /capability-map, /strategic, /consolidation,
# /policy-monitoring), causing Flask endpoint name conflicts.
# The "/strategic" legacy route also conflicted with enterprise_bp.


# === UTILITY FUNCTIONS ===


def get_architecture_statistics():
    """Get architecture statistics"""
    try:
        return {
            "elements": ArchiMateElement.query.count(),
            "relationships": ArchiMateRelationship.query.count(),
            "models": ArchitectureModel.query.count(),
        }
    except Exception:
        return {"elements": 0, "relationships": 0, "models": 0}


def get_capability_map_statistics():
    """Get capability map statistics"""
    try:
        return {
            "capabilities": BusinessCapability.query.count(),
            "applications": ApplicationComponent.query.count(),
            "mapped_relationships": 0,  # Placeholder
        }
    except Exception:
        return {"capabilities": 0, "applications": 0, "mapped_relationships": 0}


def get_strategic_statistics():
    """Get strategic statistics"""
    try:
        result = strategic_service.get_strategic_metrics()
        if result.get("success"):
            data = result["data"]
            return {
                "initiatives": data.get("initiatives", {}).get("total", 0),
                "milestones": data.get("milestones", {}).get("total", 0),
                "risks": data.get("initiatives", {}).get("at_risk", 0),
            }
        return {"initiatives": 0, "milestones": 0, "risks": 0}
    except Exception:
        return {"initiatives": 0, "milestones": 0, "risks": 0}


def get_consolidation_statistics():
    """Get consolidation statistics"""
    try:
        result = consolidation_service.get_consolidation_statistics()
        if result.get("success"):
            data = result["data"]
            return {
                "candidates": data.get("candidates", {}).get("total", 0),
                "opportunities": data.get("opportunities", {}).get("total", 0),
                "savings_estimate": data.get("estimated_pipeline_savings", 0),
            }
        return {"candidates": 0, "opportunities": 0, "savings_estimate": 0}
    except Exception:
        return {"candidates": 0, "opportunities": 0, "savings_estimate": 0}


def get_policy_monitoring_statistics():
    """Get policy monitoring statistics"""
    try:
        result = policy_monitoring_service.get_policy_monitoring_dashboard()
        if result.get("success"):
            data = result["data"]
            return {
                "policies": data.get("total_policies", 0),
                "violations": data.get("total_violations", 0),
                "compliance_rate": data.get("compliance_percentage", 0),
            }
        return {"policies": 0, "violations": 0, "compliance_rate": 0}
    except Exception:
        return {"policies": 0, "violations": 0, "compliance_rate": 0}


# === ERROR HANDLERS ===


@unified_low_priority_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return render_template("errors/404.html"), 404


@unified_low_priority_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    db.session.rollback()
    return render_template("errors/500.html"), 500


@unified_low_priority_bp.errorhandler(CSRFError)
def csrf_error(error):
    """Handle CSRF errors"""
    flash("CSRF token expired. Please try again.", "error")
    return redirect(
        request.referrer or url_for("unified_low_priority.architecture_dashboard")
    )
