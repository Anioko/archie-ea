"""
Coverage Matrix API Routes - LLM-PRD - 04 Implementation

RESTful API endpoints for interactive coverage matrix with heatmap visualization,
gap analysis modal, and AI-powered coverage estimation.
"""

import logging
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import login_required
from sqlalchemy import func

from app import db
from app.models.vendor.vendor_organization import VendorOrganization  # noqa: E402,F401
from app.decorators import audit_log
from app.models.business_capabilities import BusinessCapability
from app.models.vendor.vendor_organization import VendorProduct
from app.services.interactive_coverage_matrix import (
    InteractiveCoverageMatrix,
    generate_coverage_matrix,
)

logger = logging.getLogger(__name__)

# Create Blueprint
coverage_matrix_bp = Blueprint("coverage_matrix", __name__, url_prefix="/api/coverage-matrix")


@coverage_matrix_bp.route("/generate", methods=["POST"])
@login_required
@audit_log("coverage_matrix_generate")
def generate_matrix():
    """
    Generate interactive coverage matrix with heatmap visualization.

    Request Body:
    {
        "capability_ids": [1, 2, 3],
        "vendor_ids": [1, 2, 3],
        "filters": {
            "vendor_categories": ["ERP", "CRM"],
            "capability_domains": ["Finance", "Operations"],
            "minimum_coverage": 60,
            "minimum_maturity": 2,
            "strategic_tiers": ["strategic", "preferred"],
            "deployment_models": ["cloud", "hybrid"]
        },
        "include_ai_estimation": true,
        "max_vendors": 20,
        "max_capabilities": 50
    }

    Response:
    {
        "success": true,
        "data": {
            "matrix_metadata": {...},
            "capabilities": [...],
            "vendors": [...],
            "coverage_matrix": [...],
            "matrix_statistics": {...},
            "visualization_data": {...},
            "interactive_elements": {...},
            "color_legend": [...],
            "filter_options": {...}
        }
    }
    """
    try:
        data = request.get_json() or {}

        # Extract parameters
        capability_ids = data.get("capability_ids")
        vendor_ids = data.get("vendor_ids")
        filters_data = data.get("filters")
        include_ai_estimation = data.get("include_ai_estimation", True)
        max_vendors = data.get("max_vendors", 20)
        max_capabilities = data.get("max_capabilities", 50)

        # Create filter object
        filters = None
        if filters_data:
            from app.services.interactive_coverage_matrix import MatrixFilter

            filters = MatrixFilter(
                vendor_categories=filters_data.get("vendor_categories", []),
                capability_domains=filters_data.get("capability_domains", []),
                minimum_coverage=filters_data.get("minimum_coverage", 0),
                minimum_maturity=filters_data.get("minimum_maturity", 1),
                strategic_tiers=filters_data.get("strategic_tiers", []),
                deployment_models=filters_data.get("deployment_models", []),
            )

        # Initialize coverage matrix service
        service = InteractiveCoverageMatrix()

        # Generate matrix
        results = service.generate_coverage_matrix(
            capability_ids=capability_ids,
            vendor_ids=vendor_ids,
            filters=filters,
            include_ai_estimation=include_ai_estimation,
            max_vendors=max_vendors,
            max_capabilities=max_capabilities,
        )

        return jsonify({"success": True, "data": results})

    except Exception as e:
        logger.error(f"Coverage matrix generation error: {e}")
        return (
            jsonify({"success": False, "error": f"Coverage matrix generation failed: {str(e)}"}),
            500,
        )


@coverage_matrix_bp.route("/gap-analysis", methods=["POST"])
@login_required
@audit_log("coverage_gap_analysis")
def get_gap_analysis():
    """
    Get detailed gap analysis for a specific vendor-capability combination.

    Request Body:
    {
        "vendor_id": 1,
        "product_id": 1,
        "capability_id": 1
    }

    Response:
    {
        "success": true,
        "data": {
            "vendor_name": "SAP SE",
            "product_name": "SAP S/4HANA Cloud",
            "capability_name": "Financial Management",
            "current_coverage": 85,
            "identified_gaps": ["gap1", "gap2"],
            "workarounds": ["workaround1", "workaround2"],
            "implementation_options": ["option1", "option2"],
            "estimated_effort": "medium",
            "risk_factors": ["risk1", "risk2"],
            "recommendations": ["recommendation1", "recommendation2"],
            "evidence_sources": ["source1", "source2"],
            "ai_estimation_confidence": 0.8
        }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No request data provided"}), 400

        vendor_id = data.get("vendor_id")
        product_id = data.get("product_id")
        capability_id = data.get("capability_id")

        if not all([vendor_id, product_id, capability_id]):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "vendor_id, product_id, and capability_id are required",
                    }
                ),
                400,
            )

        # Initialize coverage matrix service
        service = InteractiveCoverageMatrix()

        # Get gap analysis
        gap_analysis = service.get_gap_analysis(vendor_id, product_id, capability_id)

        return jsonify(
            {
                "success": True,
                "data": {
                    "vendor_name": gap_analysis.vendor_name,
                    "product_name": gap_analysis.product_name,
                    "capability_name": gap_analysis.capability_name,
                    "current_coverage": gap_analysis.current_coverage,
                    "identified_gaps": gap_analysis.identified_gaps,
                    "workarounds": gap_analysis.workarounds,
                    "implementation_options": gap_analysis.implementation_options,
                    "estimated_effort": gap_analysis.estimated_effort,
                    "risk_factors": gap_analysis.risk_factors,
                    "recommendations": gap_analysis.recommendations,
                    "evidence_sources": gap_analysis.evidence_sources,
                    "ai_estimation_confidence": gap_analysis.ai_estimation_confidence,
                },
            }
        )

    except Exception as e:
        logger.error(f"Gap analysis error: {e}")
        return jsonify({"success": False, "error": "Gap analysis failed"}), 500


@coverage_matrix_bp.route("/estimate-coverage", methods=["POST"])
@login_required
@audit_log("coverage_estimate")
def estimate_coverage():
    """
    Estimate coverage percentage from product description using AI.

    Request Body:
    {
        "vendor_product_id": 1,
        "capability_id": 1
    }

    Response:
    {
        "success": true,
        "data": {
            "estimated_coverage": 75,
            "confidence_level": "high",
            "reasoning": "Based on product features...",
            "identified_strengths": ["strength1", "strength2"],
            "potential_gaps": ["gap1", "gap2"],
            "estimation_method": "ai_powered",
            "generated_at": "2024 - 01 - 20T10:30:00Z"
        }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No request data provided"}), 400

        vendor_product_id = data.get("vendor_product_id")
        capability_id = data.get("capability_id")

        if not all([vendor_product_id, capability_id]):
            return (
                jsonify(
                    {"success": False, "error": "vendor_product_id and capability_id are required"}
                ),
                400,
            )

        # Initialize coverage matrix service
        service = InteractiveCoverageMatrix()

        # Estimate coverage
        estimation = service.estimate_coverage_from_description(vendor_product_id, capability_id)

        return jsonify({"success": True, "data": estimation})

    except Exception as e:
        logger.error(f"Coverage estimation error: {e}")
        return jsonify({"success": False, "error": "Coverage estimation failed"}), 500


@coverage_matrix_bp.route("/capabilities", methods=["GET"])
@login_required
def get_capabilities():
    """
    Get available capabilities for the coverage matrix.

    Query Parameters:
    - domain: Filter by domain (optional)
    - level: Filter by level (optional)
    - limit: Maximum number of results (default: 100)
    - offset: Pagination offset (default: 0)

    Response:
    {
        "success": true,
        "data": {
            "capabilities": [
                {
                    "id": 1,
                    "name": "Financial Management",
                    "description": "Core financial processes...",
                    "domain": "Finance",
                    "level": 1
                }
            ],
            "total": 150,
            "domains": ["Finance", "Operations", "Customer"],
            "levels": [1, 2, 3, 4, 5]
        }
    }
    """
    try:
        # Get query parameters
        domain = request.args.get("domain")
        level = request.args.get("level", type=int)
        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)

        # Build query
        query = BusinessCapability.query

        if domain:
            query = query.filter(BusinessCapability.business_domain == domain)

        if level:
            query = query.filter(BusinessCapability.level == level)

        # Get total count
        total = query.count()

        # Get capabilities
        capabilities = query.order_by(BusinessCapability.name).offset(offset).limit(limit).all()

        # Get available domains and levels
        domains = db.session.query(BusinessCapability.business_domain).distinct().all()
        levels = db.session.query(BusinessCapability.level).distinct().all()

        # Format results
        capability_list = []
        for cap in capabilities:
            capability_list.append(
                {
                    "id": cap.id,
                    "name": cap.name,
                    "description": cap.description,
                    "domain": cap.business_domain,
                    "level": cap.level,
                }
            )

        return jsonify(
            {
                "success": True,
                "data": {
                    "capabilities": capability_list,
                    "total": total,
                    "domains": [d[0] for d in domains if d[0]],
                    "levels": [l[0] for l in levels if l[0]],
                },
            }
        )

    except Exception as e:
        logger.error(f"Get capabilities error: {e}")
        return jsonify({"success": False, "error": "Failed to get capabilities"}), 500


@coverage_matrix_bp.route("/vendors", methods=["GET"])
@login_required
def get_vendors():
    """
    Get available vendors for the coverage matrix.

    Query Parameters:
    - category: Filter by category (optional)
    - strategic_tier: Filter by strategic tier (optional)
    - limit: Maximum number of results (default: 50)
    - offset: Pagination offset (default: 0)

    Response:
    {
        "success": true,
        "data": {
            "vendors": [
                {
                    "id": 1,
                    "name": "SAP SE",
                    "category": "ERP",
                    "strategic_tier": "strategic",
                    "product_count": 2
                }
            ],
            "total": 156,
            "categories": ["ERP", "CRM", "HCM"],
            "strategic_tiers": ["strategic", "preferred", "approved"]
        }
    }
    """
    try:
        # Get query parameters
        category = request.args.get("category")
        strategic_tier = request.args.get("strategic_tier")
        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)

        # Build query
        query = (
            db.session.query(
                VendorOrganization, func.count(VendorProduct.id).label("product_count")
            )
            .outerjoin(VendorProduct)
            .group_by(VendorOrganization.id)
        )

        if category:
            query = query.filter(VendorOrganization.vendor_type == category)

        if strategic_tier:
            query = query.filter(VendorOrganization.strategic_tier == strategic_tier)

        # Get total count
        total = query.count()

        # Get vendors
        vendors = query.order_by(VendorOrganization.name).offset(offset).limit(limit).all()

        # Get available categories and strategic tiers
        categories = db.session.query(VendorOrganization.vendor_type).distinct().all()
        strategic_tiers = db.session.query(VendorOrganization.strategic_tier).distinct().all()

        # Format results
        vendor_list = []
        for vendor, product_count in vendors:
            vendor_list.append(
                {
                    "id": vendor.id,
                    "name": vendor.name,
                    "category": vendor.vendor_type,
                    "strategic_tier": vendor.strategic_tier,
                    "product_count": product_count,
                }
            )

        return jsonify(
            {
                "success": True,
                "data": {
                    "vendors": vendor_list,
                    "total": total,
                    "categories": [c[0] for c in categories if c[0]],
                    "strategic_tiers": [t[0] for t in strategic_tiers if t[0]],
                },
            }
        )

    except Exception as e:
        logger.error(f"Get vendors error: {e}")
        return jsonify({"success": False, "error": "Failed to get vendors"}), 500


@coverage_matrix_bp.route("/matrix-data", methods=["GET"])
@login_required
def get_matrix_data():
    """
    Get pre-computed matrix data for quick loading.

    Query Parameters:
    - matrix_type: "overview" or "detailed" (default: "overview")
    - refresh: Force refresh of cached data (default: false)

    Response:
    {
        "success": true,
        "data": {
            "matrix_type": "overview",
            "total_vendors": 20,
            "total_capabilities": 50,
            "matrix_cells": 1000,
            "last_updated": "2024 - 01 - 20T10:30:00Z",
            "coverage_summary": {
                "high_coverage": 400,
                "medium_coverage": 350,
                "low_coverage": 250
            }
        }
    }
    """
    try:
        # Get query parameters
        matrix_type = request.args.get("matrix_type", "overview")
        force_refresh = request.args.get("refresh", "false").lower() == "true"

        # Initialize coverage matrix service
        service = InteractiveCoverageMatrix()

        if matrix_type == "overview":
            # Generate overview matrix with limited data
            matrix_data = service.generate_coverage_matrix(
                max_vendors=10,
                max_capabilities=20,
                include_ai_estimation=False,  # Skip AI for overview
            )
        else:
            # Generate detailed matrix
            matrix_data = service.generate_coverage_matrix(
                max_vendors=50, max_capabilities=100, include_ai_estimation=True
            )

        # Create summary data
        summary_data = {
            "matrix_type": matrix_type,
            "total_vendors": matrix_data["matrix_metadata"]["total_vendors"],
            "total_capabilities": matrix_data["matrix_metadata"]["total_capabilities"],
            "matrix_cells": matrix_data["matrix_metadata"]["matrix_cells"],
            "last_updated": matrix_data["matrix_metadata"]["generated_at"],
            "coverage_summary": matrix_data["matrix_statistics"]["coverage_distribution"],
        }

        return jsonify({"success": True, "data": summary_data})

    except Exception as e:
        logger.error(f"Get matrix data error: {e}")
        return jsonify({"success": False, "error": "Failed to get matrix data"}), 500


@coverage_matrix_bp.route("/export", methods=["POST"])
@login_required
@audit_log("coverage_matrix_export")
def export_matrix():
    """
    Export coverage matrix data in various formats.

    Request Body:
    {
        "matrix_data": {...},
        "format": "excel",
        "include_charts": true,
        "include_gap_analysis": false
    }

    Response:
    {
        "success": true,
        "data": {
            "download_url": "/downloads/coverage_matrix_123.xlsx",
            "format": "excel",
            "file_size": 2048000,
            "expires_at": "2024 - 01 - 21T10:30:00Z"
        }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No request data provided"}), 400

        matrix_data = data.get("matrix_data")
        export_format = data.get("format", "excel")
        include_charts = data.get("include_charts", True)
        include_gap_analysis = data.get("include_gap_analysis", False)

        if not matrix_data:
            return jsonify({"success": False, "error": "matrix_data is required"}), 400

        # Generate export (placeholder - would implement actual export logic)
        export_filename = (
            f"coverage_matrix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_format}"
        )
        export_url = f"/downloads/{export_filename}"

        return jsonify(
            {
                "success": True,
                "data": {
                    "download_url": export_url,
                    "format": export_format,
                    "file_size": 2048000,  # Placeholder
                    "expires_at": datetime.utcnow()
                    .replace(hour=datetime.utcnow().hour + 24)
                    .isoformat(),
                },
            }
        )

    except Exception as e:
        logger.error(f"Matrix export error: {e}")
        return jsonify({"success": False, "error": "Matrix export failed"}), 500


@coverage_matrix_bp.route("/health", methods=["GET"])
@login_required
def health_check():
    """
    Health check endpoint for coverage matrix service.

    Response:
    {
        "success": true,
        "data": {
            "status": "healthy",
            "database_connected": true,
            "ai_service_available": true,
            "total_capabilities": 150,
            "total_vendors": 156,
            "service_version": "1.0.0"
        }
    }
    """
    try:
        # Check database connection
        db_connected = db.session.execute(db.text("SELECT 1")).scalar() == 1  # tenant-exempt: health check

        # Check AI service availability
        ai_service_available = True  # Placeholder - would check actual AI service

        # Get statistics
        total_capabilities = BusinessCapability.query.count()
        total_vendors = db.session.query(VendorOrganization).count()

        health_status = {
            "status": "healthy" if db_connected else "unhealthy",
            "database_connected": db_connected,
            "ai_service_available": ai_service_available,
            "total_capabilities": total_capabilities,
            "total_vendors": total_vendors,
            "service_version": "1.0.0",
        }

        return jsonify({"success": True, "data": health_status})

    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({"success": False, "error": "Health check failed"}), 500


@coverage_matrix_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({"success": False, "error": "Endpoint not found"}), 404


@coverage_matrix_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    db.session.rollback()
    return jsonify({"success": False, "error": "Internal server error"}), 500
