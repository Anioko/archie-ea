"""
MIGRATION: Copied from app/api/vendor_discovery_routes.py
Changes: `from app import db` -> `from app.extensions import db`
Legacy file preserved at original location.

Vendor Discovery API Routes - PRD-V01 Implementation
"""

import logging

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.decorators import audit_log
from app.extensions import db
from app.models.business_capabilities import BusinessCapability
from app.modules.vendors.services.vendor_discovery_engine import VendorDiscoveryEngine

logger = logging.getLogger(__name__)

# Create blueprint
vendor_discovery_bp = Blueprint("vendor_discovery", __name__, url_prefix="/api/vendor-discovery")


@vendor_discovery_bp.route("/discover", methods=["POST"])
@login_required
@audit_log("vendor_discover")
def discover_vendors():
    """Discover vendors for capability requirements with AI-powered recommendations."""
    try:
        data = request.get_json()

        if not data or "capability_requirements" not in data:
            return jsonify({"success": False, "error": "capability_requirements are required"}), 400

        capability_requirements = data["capability_requirements"]
        org_context = data.get("organization_context", {})
        constraints = data.get("constraints", {})

        if not capability_requirements or not isinstance(capability_requirements, list):
            return (
                jsonify(
                    {"success": False, "error": "capability_requirements must be a non-empty array"}
                ),
                400,
            )

        organization_size = org_context.get("size", "medium")
        industry = org_context.get("industry", "general")
        deployment_preference = org_context.get("deployment_preference", "cloud")
        user_count = org_context.get("user_count", 1000)
        tco_period_years = org_context.get("tco_period_years", 5)

        budget_range = None
        if constraints.get("budget_range"):
            budget_data = constraints["budget_range"]
            from decimal import Decimal

            budget_range = (
                Decimal(str(budget_data.get("min", 0))),
                Decimal(str(budget_data.get("max", 999999999))),
            )

        engine = VendorDiscoveryEngine()

        discovery_results = engine.discover_vendors_for_capabilities(
            capability_requirements=capability_requirements,
            organization_size=organization_size,
            industry=industry,
            budget_range=budget_range,
            deployment_preference=deployment_preference,
            user_count=user_count,
            tco_period_years=tco_period_years,
        )

        return jsonify({"success": True, "discovery_results": discovery_results})

    except Exception as e:
        logger.error(f"Error in vendor discovery: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@vendor_discovery_bp.route("/capabilities", methods=["GET"])
@login_required
def get_capabilities():
    """Get available business capabilities for vendor discovery."""
    try:
        domain = request.args.get("domain")
        level = request.args.get("level")
        search = request.args.get("search", "").strip()

        query = db.session.query(BusinessCapability)

        if domain:
            query = query.filter(BusinessCapability.business_domain == domain)

        if level:
            try:
                level_int = int(level)
                query = query.filter(BusinessCapability.level == level_int)
            except ValueError:
                pass

        if search:
            query = query.filter(BusinessCapability.name.ilike(f"%{search}%"))

        query = query.order_by(BusinessCapability.name)

        capabilities = query.all()

        capabilities_data = []
        for cap in capabilities:
            capabilities_data.append(
                {
                    "id": cap.id,
                    "name": cap.name,
                    "description": cap.description,
                    "level": cap.level,
                    "business_domain": cap.business_domain,
                    "category": cap.category,
                    "criticality": cap.strategic_importance,
                }
            )

        return jsonify(
            {
                "success": True,
                "capabilities": capabilities_data,
                "total": len(capabilities_data),
                "filters": {"domain": domain, "level": level, "search": search},
            }
        )

    except Exception as e:
        logger.error(f"Error getting capabilities: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@vendor_discovery_bp.route("/calculate-tco", methods=["POST"])
@login_required
@audit_log("vendor_tco_calculate")
def calculate_tco():
    """Calculate TCO for specific vendor products."""
    try:
        data = request.get_json()

        if not data or "vendor_products" not in data:
            return jsonify({"success": False, "error": "vendor_products array is required"}), 400

        vendor_products = data["vendor_products"]

        if not isinstance(vendor_products, list) or not vendor_products:
            return (
                jsonify({"success": False, "error": "vendor_products must be a non-empty array"}),
                400,
            )

        engine = VendorDiscoveryEngine()
        tco_results = []

        for product_config in vendor_products:
            try:
                from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct

                vendor = VendorOrganization.query.get(product_config["vendor_id"])
                product = VendorProduct.query.get(product_config["product_id"])

                if not vendor or not product:
                    tco_results.append(
                        {
                            "vendor_id": product_config["vendor_id"],
                            "product_id": product_config["product_id"],
                            "error": "Vendor or product not found",
                        }
                    )
                    continue

                tco_calculation = engine._calculate_tco(
                    vendor=vendor,
                    product=product,
                    user_count=product_config.get("user_count", 1000),
                    tco_period_years=product_config.get("tco_period_years", 5),
                    deployment_preference=product_config.get("deployment_preference", "cloud"),
                )

                tco_results.append(
                    {
                        "vendor_id": product_config["vendor_id"],
                        "product_id": product_config["product_id"],
                        "vendor_name": vendor.name,
                        "product_name": product.name,
                        "tco": {
                            "total_tco": float(tco_calculation.total_tco)
                            if tco_calculation.total_tco
                            else 0,
                            "annual_average": float(tco_calculation.annual_average)
                            if tco_calculation.annual_average
                            else 0,
                            "per_user_annual": float(tco_calculation.per_user_annual)
                            if tco_calculation.per_user_annual
                            else 0,
                            "vs_industry_percentage": tco_calculation.vs_industry_percentage or 0,
                            "confidence_level": tco_calculation.confidence_level or "medium",
                            "yearly_breakdown": tco_calculation.get_yearly_breakdown(),
                        },
                    }
                )

            except Exception as e:
                logger.error(
                    f"Error calculating TCO for product {product_config.get('product_id')}: {e}"
                )
                tco_results.append(
                    {
                        "vendor_id": product_config.get("vendor_id"),
                        "product_id": product_config.get("product_id"),
                        "error": "An internal error occurred",
                    }
                )

        return jsonify({"success": True, "tco_results": tco_results})

    except Exception as e:
        logger.error(f"Error in TCO calculation: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@vendor_discovery_bp.route("/compare-vendors", methods=["POST"])
@login_required
@audit_log("vendor_compare")
def compare_vendors():
    """Compare multiple vendors across multiple dimensions."""
    try:
        data = request.get_json()

        if not data or "vendor_products" not in data:
            return jsonify({"success": False, "error": "vendor_products array is required"}), 400

        vendor_products = data["vendor_products"]
        comparison_criteria = data.get("comparison_criteria", {})

        engine = VendorDiscoveryEngine()
        comparison_results = []

        for product_config in vendor_products:
            try:
                from app.models.vendor.vendor_organization import (
                    VendorOrganization,
                    VendorProduct,
                    VendorProductCapability,
                )

                vendor = VendorOrganization.query.get(product_config["vendor_id"])
                product = VendorProduct.query.get(product_config["product_id"])

                if not vendor or not product:
                    continue

                capability_ids = comparison_criteria.get("capability_ids", [])
                capability_coverage = []

                if capability_ids:
                    capabilities = (
                        db.session.query(VendorProductCapability, BusinessCapability)
                        .join(
                            BusinessCapability,
                            VendorProductCapability.business_capability_id == BusinessCapability.id,
                        )
                        .filter(
                            VendorProductCapability.vendor_product_id == product.id,
                            VendorProductCapability.business_capability_id.in_(capability_ids),
                        )
                        .all()
                    )

                    for vpc, cap in capabilities:
                        capability_coverage.append(
                            {
                                "capability_id": cap.id,
                                "capability_name": cap.name,
                                "coverage_percentage": vpc.coverage_percentage,
                                "maturity_level": vpc.maturity_level,
                                "implementation_complexity": vpc.implementation_complexity,
                            }
                        )

                tco_calculation = engine._calculate_tco(
                    vendor=vendor,
                    product=product,
                    user_count=comparison_criteria.get("user_count", 1000),
                    tco_period_years=comparison_criteria.get("tco_period_years", 5),
                    deployment_preference=comparison_criteria.get("deployment_preference", "cloud"),
                )

                candidate_data = {
                    "vendor": vendor,
                    "product": product,
                    "matched_capabilities": capability_coverage,
                }

                scores = engine._score_vendors(
                    [candidate_data],
                    [{"capability_id": cid, "importance": "medium"} for cid in capability_ids],
                    comparison_criteria.get("organization_size", "medium"),
                    comparison_criteria.get("industry", "general"),
                )

                vendor_score = scores[0] if scores else {"scores": {}}

                comparison_results.append(
                    {
                        "vendor_id": vendor.id,
                        "product_id": product.id,
                        "vendor_name": vendor.name,
                        "product_name": product.name,
                        "strategic_tier": vendor.strategic_tier,
                        "partnership_level": vendor.partnership_level,
                        "gartner_quadrant": vendor.gartner_magic_quadrant,
                        "capability_coverage": capability_coverage,
                        "scores": vendor_score.get("scores", {}),
                        "tco": {
                            "total_tco": float(tco_calculation.total_tco)
                            if tco_calculation.total_tco
                            else 0,
                            "annual_average": float(tco_calculation.annual_average)
                            if tco_calculation.annual_average
                            else 0,
                            "per_user_annual": float(tco_calculation.per_user_annual)
                            if tco_calculation.per_user_annual
                            else 0,
                            "vs_industry_percentage": tco_calculation.vs_industry_percentage or 0,
                        },
                    }
                )

            except Exception as e:
                logger.error(
                    f"Error comparing vendor product {product_config.get('product_id')}: {e}"
                )
                continue

        return jsonify({"success": True, "comparison_results": comparison_results})

    except Exception as e:
        logger.error(f"Error in vendor comparison: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@vendor_discovery_bp.route("/recommendations/<int:vendor_id>/<int:product_id>", methods=["GET"])
@login_required
def get_vendor_recommendations(vendor_id, product_id):
    """Get detailed recommendations for a specific vendor product."""
    try:
        from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct

        vendor = VendorOrganization.query.get(vendor_id)
        product = VendorProduct.query.get(product_id)

        if not vendor or not product:
            return jsonify({"success": False, "error": "Vendor or product not found"}), 404

        engine = VendorDiscoveryEngine()

        from app.models.vendor.vendor_organization import VendorProductCapability

        capabilities = (
            db.session.query(VendorProductCapability, BusinessCapability)
            .join(
                BusinessCapability,
                VendorProductCapability.business_capability_id == BusinessCapability.id,
            )
            .filter(VendorProductCapability.vendor_product_id == product.id)
            .all()
        )

        capability_requirements = []
        for vpc, cap in capabilities:
            capability_requirements.append(
                {
                    "capability_id": cap.id,
                    "capability_name": cap.name,
                    "min_coverage": 70,
                    "importance": "medium",
                }
            )

        discovery_results = engine.discover_vendors_for_capabilities(
            capability_requirements=capability_requirements,
            organization_size="medium",
            industry="general",
            budget_range=None,
            deployment_preference="cloud",
            user_count=1000,
            tco_period_years=5,
        )

        vendor_result = None
        for candidate in discovery_results["all_candidates"]:
            if candidate["vendor"].id == vendor_id and candidate["product"].id == product_id:
                vendor_result = candidate
                break

        if not vendor_result:
            return (
                jsonify(
                    {"success": False, "error": "Vendor product not found in discovery results"}
                ),
                404,
            )

        return jsonify(
            {
                "success": True,
                "vendor_recommendations": {
                    "vendor": vendor_result["vendor"],
                    "product": vendor_result["product"],
                    "scores": vendor_result["scores"],
                    "recommendation_strength": vendor_result["recommendation_strength"],
                    "tco": vendor_result.get("tco", {}),
                    "key_strengths": engine._identify_key_strengths(vendor_result),
                    "potential_concerns": engine._identify_concerns(vendor_result),
                    "next_steps": engine._suggest_next_steps(
                        vendor_result, vendor_result["scores"]
                    ),
                    "capability_coverage": vendor_result["matched_capabilities"],
                },
            }
        )

    except Exception as e:
        logger.error(f"Error getting vendor recommendations: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


def register_vendor_discovery_routes(app):
    """Register vendor discovery blueprint with Flask app."""
    app.register_blueprint(vendor_discovery_bp)
    logger.info("Vendor discovery API routes registered")
