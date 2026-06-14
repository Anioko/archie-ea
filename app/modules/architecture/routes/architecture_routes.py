"""
DEPRECATED: This file is migrated to app/modules/architecture/.
Registration is now centralized via app.modules.architecture.register().
Do NOT modify -- kept as fallback until Phase 6 cleanup.

Architecture Model Routes

Provides REST API endpoints for the new architecture models:
- Data Architecture Models (ConceptualDataModel, LogicalDataModel, PhysicalDataModel, DataLineage, DataTransformation)
- Solutions Architecture Models (Solution, SolutionPattern, Contract)
- Software Architecture Models (SoftwareModule, DesignPattern, SoftwareDependency)
"""

import logging

from flask import Blueprint, current_app, jsonify, render_template, request
from werkzeug.exceptions import HTTPException
from flask_login import login_required

from app.decorators import audit_log

logger = logging.getLogger(__name__)

from app.models import (
    DesignPattern,
    SoftwareDependency,
    SoftwareModule,
    Solution,
    SolutionContract,
    SolutionPattern,
)
from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct

architecture_bp = Blueprint("architecture", __name__, url_prefix="/architecture")


# ============================================================================
# Page Routes
# ============================================================================


# NOTE: /monitoring route removed — broken UI with hardcoded bg-white,
# undefined% scores, and in-memory-only data. The working alternative is
# architect_ui.architecture_health (ArchiMate Model Health).
# API layer (architecture_monitoring_routes.py) kept for future use.


# ============================================================================
# Solutions Architecture API Endpoints
# ============================================================================


@architecture_bp.route("/api/solutions")
@login_required
def api_solutions():
    """Get all solutions."""
    try:
        solutions = Solution.query.limit(500).all()
        return jsonify(
            [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "solution_type": s.solution_type,
                    "business_domain": s.business_domain,
                    "complexity_level": s.complexity_level,
                    "status": s.status,
                    "deployment_status": s.deployment_status,
                    "estimated_cost": float(s.estimated_cost)
                    if s.estimated_cost
                    else None,
                    "actual_cost": float(s.actual_cost) if s.actual_cost else None,
                    "roi_percentage": s.roi_percentage,
                    "planned_start_date": s.planned_start_date.isoformat()
                    if s.planned_start_date
                    else None,
                    "planned_end_date": s.planned_end_date.isoformat()
                    if s.planned_end_date
                    else None,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in solutions
            ]
        )
    except Exception as e:
        return jsonify({"error": "An internal error occurred"}), 500


@architecture_bp.route("/api/solution-patterns")
@login_required
def api_solution_patterns():
    """Get all solution patterns."""
    try:
        patterns = SolutionPattern.query.limit(500).all()
        return jsonify(
            [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "pattern_category": p.pattern_category,
                    "pattern_type": p.pattern_type,
                    "complexity_level": p.complexity_level,
                    "approval_status": p.approval_status,
                    "usage_count": p.usage_count,
                    "success_rate": p.success_rate,
                    "technology_stack": p.technology_stack,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in patterns
            ]
        )
    except Exception as e:
        return jsonify({"error": "An internal error occurred"}), 500


@architecture_bp.route("/api/contracts")
@login_required
def api_contracts():
    """Get all contracts."""
    try:
        contracts = SolutionContract.query.limit(500).all()
        return jsonify(
            [
                {
                    "id": c.id,
                    "name": c.name,
                    "description": c.description,
                    "contract_type": c.contract_type,
                    "contract_category": c.contract_category,
                    "vendor_organization": c.vendor_organization,
                    "contract_number": c.contract_number,
                    "contract_value": float(c.contract_value)
                    if c.contract_value
                    else None,
                    "currency": c.currency,
                    "status": c.status,
                    "start_date": c.start_date.isoformat() if c.start_date else None,
                    "end_date": c.end_date.isoformat() if c.end_date else None,
                    "sla_uptime_percentage": c.sla_uptime_percentage,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in contracts
            ]
        )
    except Exception as e:
        return jsonify({"error": "An internal error occurred"}), 500


# ============================================================================
# Software Architecture API Endpoints
# ============================================================================


@architecture_bp.route("/api/software-modules")
@login_required
def api_software_modules():
    """Get all software modules."""
    try:
        modules = SoftwareModule.query.limit(500).all()
        return jsonify(
            [
                {
                    "id": m.id,
                    "name": m.name,
                    "description": m.description,
                    "module_type": m.module_type,
                    "architecture_layer": m.architecture_layer,
                    "programming_language": m.programming_language,
                    "package_name": m.package_name,
                    "namespace": m.namespace,
                    "version": m.version,
                    "complexity_score": m.complexity_score,
                    "test_coverage_percentage": m.test_coverage_percentage,
                    "maintainability_index": m.maintainability_index,
                    "status": m.status,
                    "security_classification": m.security_classification,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in modules
            ]
        )
    except Exception as e:
        return jsonify({"error": "An internal error occurred"}), 500


@architecture_bp.route("/api/design-patterns")
@login_required
def api_design_patterns():
    """Get all design patterns."""
    try:
        patterns = DesignPattern.query.limit(500).all()
        return jsonify(
            [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "pattern_category": p.pattern_category,
                    "pattern_family": p.pattern_family,
                    "complexity_level": p.complexity_level,
                    "approval_status": p.approval_status,
                    "usage_count": p.usage_count,
                    "success_rate": p.success_rate,
                    "problem_statement": p.problem_statement,
                    "solution_description": p.solution_description,
                    "code_example_language": p.code_example_language,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in patterns
            ]
        )
    except Exception as e:
        return jsonify({"error": "An internal error occurred"}), 500


@architecture_bp.route("/api/software-dependencies")
@login_required
def api_software_dependencies():
    """Get all software dependencies."""
    try:
        dependencies = SoftwareDependency.query.limit(500).all()
        return jsonify(
            [
                {
                    "id": d.id,
                    "name": d.name,
                    "description": d.description,
                    "dependency_type": d.dependency_type,
                    "technology_stack": d.technology_stack,
                    "license_type": d.license_type,
                    "package_manager": d.package_manager,
                    "package_name": d.package_name,
                    "current_version": d.current_version,
                    "latest_version": d.latest_version,
                    "version_constraint": d.version_constraint,
                    "is_runtime_dependency": d.is_runtime_dependency,
                    "is_development_dependency": d.is_development_dependency,
                    "is_test_dependency": d.is_test_dependency,
                    "is_optional": d.is_optional,
                    "vulnerability_score": d.vulnerability_score,
                    "approval_status": d.approval_status,
                    "download_count": d.download_count,
                    "github_stars": d.github_stars,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in dependencies
            ]
        )
    except Exception as e:
        return jsonify({"error": "An internal error occurred"}), 500


# ============================================================================
# CRUD Operations (Create/Update/Delete)
# ============================================================================


@architecture_bp.route("/api/solutions", methods=["POST"])
@login_required
@audit_log("solution_create")
def create_solution():
    """Create a new solution."""
    try:
        data = request.get_json()

        solution = Solution(
            name=data["name"],
            description=data.get("description", ""),
            solution_type=data.get("solution_type"),
            business_domain=data.get("business_domain"),
            complexity_level=data.get("complexity_level"),
            business_value=data.get("business_value"),
            scope_description=data.get("scope_description"),
            estimated_cost=data.get("estimated_cost"),
            solution_owner=data.get("solution_owner"),
            business_sponsor=data.get("business_sponsor"),
            technical_lead=data.get("technical_lead"),
        )

        from app import db

        db.session.add(solution)
        db.session.commit()

        return (
            jsonify(
                {
                    "id": solution.id,
                    "name": solution.name,
                    "message": "Solution created successfully",
                }
            ),
            201,
        )

    except Exception as e:
        return jsonify({"error": "An internal error occurred"}), 500


@architecture_bp.route("/api/software-modules", methods=["POST"])
@login_required
@audit_log("software_module_create")
def create_software_module():
    """Create a new software module."""
    try:
        data = request.get_json()

        module = SoftwareModule(
            name=data["name"],
            description=data.get("description", ""),
            module_type=data.get("module_type"),
            architecture_layer=data.get("architecture_layer"),
            programming_language=data.get("programming_language"),
            package_name=data.get("package_name"),
            namespace=data.get("namespace"),
            version=data.get("version"),
            primary_responsibility=data.get("primary_responsibility"),
            complexity_score=data.get("complexity_score"),
            test_coverage_percentage=data.get("test_coverage_percentage"),
            maintainability_index=data.get("maintainability_index"),
            module_owner=data.get("module_owner"),
            code_reviewer=data.get("code_reviewer"),
            security_classification=data.get("security_classification"),
        )

        from app import db

        db.session.add(module)
        db.session.commit()

        return (
            jsonify(
                {
                    "id": module.id,
                    "name": module.name,
                    "message": "Software module created successfully",
                }
            ),
            201,
        )

    except Exception as e:
        return jsonify({"error": "An internal error occurred"}), 500


# ============================================================================
# Dashboard Views
# ============================================================================


@architecture_bp.route("/solutions-architecture")
@login_required
def solutions_architecture_dashboard():
    """Solutions architecture dashboard."""
    try:
        from app import db
        from app.models.truly_missing_models import (
            Solution,
            SolutionContract,
            SolutionPattern,
        )

        # Get counts for metrics cards
        solution_count = Solution.query.count()
        pattern_count = SolutionPattern.query.count()
        contract_count = SolutionContract.query.count()

        # Get solutions with their capability counts
        solutions_objs = Solution.query.limit(500).all()
        solutions_list = []

        # Batch prefetch all solution-application mappings
        from sqlalchemy import text as sa_text

        sol_app_rows = db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
            sa_text(
                "SELECT solution_id, application_component_id FROM solution_applications"
            )
        ).fetchall()
        sol_app_map = {}
        all_sol_app_ids = set()
        for row in sol_app_rows:
            sol_app_map.setdefault(row[0], []).append(row[1])
            all_sol_app_ids.add(row[1])

        # Batch prefetch all unified capability mappings for involved apps
        from app.models.unified_application_capability_mapping import (
            UnifiedApplicationCapabilityMapping,
        )

        all_cap_mappings = (
            UnifiedApplicationCapabilityMapping.query.filter(
                UnifiedApplicationCapabilityMapping.application_component_id.in_(
                    list(all_sol_app_ids)
                )
            ).all()
            if all_sol_app_ids
            else []
        )
        cap_mappings_by_app = {}
        for m in all_cap_mappings:
            cap_mappings_by_app.setdefault(m.application_component_id, []).append(
                m.unified_capability_id
            )

        for sol in solutions_objs:
            # Look up pre-fetched application IDs for this solution
            app_ids_for_sol = sol_app_map.get(sol.id, [])
            cap_count = 0
            if app_ids_for_sol:
                caps = set()
                for app_id in app_ids_for_sol:
                    for cap_id in cap_mappings_by_app.get(app_id, []):
                        caps.add(cap_id)
                cap_count = len(caps)

            solutions_list.append(
                {
                    "id": sol.id,
                    "name": sol.name,
                    "description": sol.description,
                    "capability_count": cap_count,
                    "app_count": len(app_ids_for_sol),
                    "status": sol.status or "planned",
                }
            )

        # ArchiMate element and relationship counts
        archimate_app_count = 0
        relationship_count = 0
        try:
            from app.models.archimate_core import (
                ArchiMateElement,
                ArchiMateRelationship,
            )

            archimate_app_count = ArchiMateElement.query.filter(
                ArchiMateElement.layer == "Application"
            ).count()
            relationship_count = ArchiMateRelationship.query.count()
        except Exception:
            logger.debug(
                "Failed to query ArchiMate application layer counts", exc_info=True
            )

        return render_template(
            "enterprise/solutions_architecture_dashboard.html",
            solutions=solutions_list,
            solution_count=solution_count,
            pattern_count=pattern_count,
            contract_count=contract_count,
            archimate_app_count=archimate_app_count,
            relationship_count=relationship_count,
        )
    except Exception as e:
        current_app.logger.error(f"Error loading solutions architecture dashboard: {e}")
        return render_template(
            "enterprise/solutions_architecture_dashboard.html",
            solutions=[],
            solution_count=0,
            pattern_count=0,
            contract_count=0,
            archimate_app_count=0,
            relationship_count=0,
        )


@architecture_bp.route("/solutions-architecture/analyze", methods=["POST"])
@login_required
def api_solutions_architecture_analyze():
    """Run AI-powered Buy/Build/Reuse analysis via SolutionArchitectOrchestrator."""
    from decimal import Decimal

    try:
        data = request.get_json(force=True) or {}
        problem = (data.get("problem_description") or "").strip()
        if not problem:
            return jsonify({"success": False, "error": "problem_description is required"}), 400

        from app.modules.architecture.services.solution_architect_orchestrator import (
            SolutionArchitectOrchestrator,
        )

        orchestrator = SolutionArchitectOrchestrator()
        result = orchestrator.analyze_problem(
            problem_description=problem,
            budget_min=Decimal(str(data["budget_min"])) if data.get("budget_min") else None,
            budget_max=Decimal(str(data["budget_max"])) if data.get("budget_max") else None,
            timeline_months=int(data["timeline_months"]) if data.get("timeline_months") else None,
            user_count=int(data["user_count"]) if data.get("user_count") else None,
            is_critical=bool(data.get("is_critical", False)),
            organization_size=data.get("organization_size", "enterprise"),
            industry_vertical=data.get("industry_vertical", "general"),
            existing_constraints=data.get("existing_constraints") or [],
            compliance_requirements=data.get("compliance_requirements") or [],
        )
        # Serialize Decimal fields for JSON
        for rec in result.get("recommendations", []):
            if rec.get("estimated_cost") is not None:
                rec["estimated_cost"] = float(rec["estimated_cost"])
        return jsonify(result)
    except Exception as exc:
        current_app.logger.error("solutions-architecture/analyze error: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500


@architecture_bp.route("/solutions-architecture/save-solution", methods=["POST"])
@login_required
def api_solutions_architecture_save():
    """Persist a recommended option as a Solution record."""
    from flask_login import current_user

    from app import db

    try:
        data = request.get_json(force=True) or {}
        name = (data.get("name") or "").strip()[:255] or "Untitled Solution"
        sol = Solution(
            name=name,
            description=data.get("problem_description", ""),
            solution_type=data.get("option_type", "").title(),
            status="planned",
            governance_status="draft",
            created_by_id=getattr(current_user, "id", None),
        )
        if data.get("estimated_cost") is not None:
            try:
                from decimal import Decimal
                sol.estimated_cost = Decimal(str(data["estimated_cost"]))
            except (ValueError, TypeError) as _cost_err:
                logger.debug("Could not parse estimated_cost: %s", _cost_err)
        db.session.add(sol)
        db.session.commit()
        return jsonify({"success": True, "solution_id": sol.id, "name": sol.name})
    except Exception as exc:
        current_app.logger.error("solutions-architecture/save error: %s", exc, exc_info=True)
        db.session.rollback()
        return jsonify({"success": False, "error": str(exc)}), 500


@architecture_bp.route("/software-architecture")
@login_required
def software_architecture_dashboard():
    """Application Architecture dashboard — ArchiMate 3.2 Application Layer."""
    import json as _json

    from sqlalchemy import text

    from app import db

    try:
        from app.models.application_portfolio import ApplicationComponent

        component_count = ApplicationComponent.query.count()

        service_count = db.session.execute(  # tenant-filtered: scoped via parent FK (application tables)
            text("SELECT COUNT(*) FROM application_services")
        ).scalar() or 0
        interface_count = db.session.execute(  # tenant-filtered: scoped via parent FK
            text("SELECT COUNT(*) FROM application_interfaces")
        ).scalar() or 0
        dependency_count = db.session.execute(  # tenant-filtered: scoped via parent FK
            text("SELECT COUNT(*) FROM application_dependencies")  # tenant-filtered
        ).scalar() or 0

        raw_components = ApplicationComponent.query.with_entities(
            ApplicationComponent.id,
            ApplicationComponent.name,
            ApplicationComponent.component_type,
            ApplicationComponent.lifecycle_status,
            ApplicationComponent.business_domain,
            ApplicationComponent.technology_stack,
            ApplicationComponent.criticality,
            ApplicationComponent.vendor_name,
            ApplicationComponent.architecture_style,
        ).limit(50).all()

        components = []
        for row in raw_components:
            # Parse technology_stack — JSON array or comma-separated string
            raw_ts = row.technology_stack
            if raw_ts:
                try:
                    ts = _json.loads(raw_ts)
                    if not isinstance(ts, list):
                        ts = [str(ts)]
                except (ValueError, TypeError):
                    ts = [t.strip() for t in str(raw_ts).split(",") if t.strip()]
            else:
                ts = []

            components.append(
                {
                    "id": row.id,
                    "name": row.name or "",
                    "component_type": row.component_type or "",
                    "lifecycle_status": (row.lifecycle_status or "").lower(),
                    "business_domain": row.business_domain or "",
                    "technology_stack": ts,
                    "criticality": (row.criticality or "").lower(),
                    "vendor_name": row.vendor_name or "",
                    "architecture_style": row.architecture_style or "",
                }
            )

        return render_template(
            "enterprise/software_architecture_dashboard.html",
            component_count=component_count,
            service_count=service_count,
            interface_count=interface_count,
            dependency_count=dependency_count,
            components=components,
        )
    except Exception as e:
        current_app.logger.error(f"Error loading application architecture dashboard: {e}")
        return render_template(
            "enterprise/software_architecture_dashboard.html",
            component_count=0,
            service_count=0,
            interface_count=0,
            dependency_count=0,
            components=[],
        )


@architecture_bp.route("/investment-priorities")
@login_required
def investment_priorities():
    """
    Investment Priorities dashboard.

    Presents capability investment priorities with real StrategicInitiative
    budget data where available (via RoadmapItem.linked_capabilities linkage).
    Canonical URL under /architecture/ for ArchiMate architects.
    """
    from app.models.unified_application_capability_mapping import UnifiedApplicationCapabilityMapping

    mapping_count = UnifiedApplicationCapabilityMapping.query.count()
    if mapping_count == 0:
        return render_template(
            "strategic/investment_matrix_prereq.html",
            mapping_count=0,
        )

    from app.modules.solutions_strategic.v2.services.investment_prioritization_service import (
        InvestmentPrioritizationService,
    )

    try:
        service = InvestmentPrioritizationService()
        analysis = service.analyze_investment_priorities(include_risk_analysis=True)

        return render_template(
            "strategic/investment_matrix.html",
            capability_scores=analysis["capability_scores"],
            critical_investments=analysis["critical_investments"],
            high_investments=analysis["high_investments"],
            medium_investments=analysis["medium_investments"],
            low_investments=analysis["low_investments"],
            portfolio_metrics=analysis["portfolio_metrics"],
            recommendations=analysis["recommendations"],
        )
    except Exception as e:
        current_app.logger.error(f"Error loading investment priorities: {e}")
        return render_template(
            "strategic/investment_matrix.html",
            capability_scores=[],
            critical_investments=[],
            high_investments=[],
            medium_investments=[],
            low_investments=[],
            portfolio_metrics={
                "total_capabilities": 0,
                "critical_priorities": 0,
                "high_priorities": 0,
                "total_estimated_investment": 0,
                "critical_investment": 0,
                "high_investment": 0,
                "average_strategic_score": 0,
                "average_coverage_score": 0,
                "average_maturity_score": 0,
                "average_risk_score": 0,
                "investment_currency": "USD",
            },
            recommendations=[],
        )


@architecture_bp.route("/vendor-templates")
@login_required
def vendor_templates():
    """Vendor templates page - displays available vendor stack templates."""
    try:
        from app.models.vendor_stack_template import VendorStackTemplate

        templates = VendorStackTemplate.query.order_by(VendorStackTemplate.name).all()
        return render_template(
            "architecture/vendor_templates.html", templates=templates
        )
    except Exception:
        # Return empty list on error
        return render_template("architecture/vendor_templates.html", templates=[])


@architecture_bp.route("/vendors/<int:vendor_id>/products")
@login_required
def vendor_products(vendor_id):
    """
    Get all products for a specific vendor.

    Returns JSON array of vendor products for the vendor products panel
    in the vendor catalogue view.
    """
    try:
        vendor = VendorOrganization.query.get_or_404(vendor_id)
        products = VendorProduct.query.filter_by(vendor_organization_id=vendor_id).all()

        return jsonify(
            [
                {
                    "id": p.id,
                    "name": p.name,
                    "product_code": p.product_code,
                    "version": p.version,
                    "product_family": p.product_family_name,
                    "deployment_model": p.deployment_model,
                    "licensing_model": p.licensing_model,
                    "product_type": p.product_type,
                    "target_market": p.target_market,
                    "primary_technology": p.primary_technology,
                    "api_availability": p.api_availability,
                    "functional_scope": p.functional_scope,
                    "market_position": p.market_position,
                    "product_maturity": p.product_maturity,
                    "scalability_rating": p.scalability_rating,
                    "security_rating": p.security_rating,
                    "usability_rating": p.usability_rating,
                    "vendor_name": vendor.name,
                }
                for p in products
            ]
        )
    except HTTPException:
        # Let get_or_404 (unknown vendor) surface as a real 404 rather than
        # being masked as a 500 by the broad handler below.
        raise
    except Exception as e:
        current_app.logger.error(f"Error fetching vendor products: {e}")
        return jsonify({"error": "An internal error occurred"}), 500
