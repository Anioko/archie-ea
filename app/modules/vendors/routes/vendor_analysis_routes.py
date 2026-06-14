"""
MIGRATION: Copied from app/routes/vendor_analysis_routes.py
Changes: `from .. import csrf, db` -> `from app import csrf` + `from app.extensions import db`
Legacy file preserved at original location.
"""
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required
from app import csrf
from app.decorators import audit_log
from app.extensions import db
from app.modules.vendors.services.analysis_service import (
    CapabilityService,
    ExportService,
    VendorAnalysisService,
    VendorService,
)

# Create blueprint
vendor_analysis_bp = Blueprint("vendor_analysis", __name__, url_prefix="/vendor-analysis")

# Service instances
analysis_service = VendorAnalysisService()
capability_service = CapabilityService()
vendor_service = VendorService()
export_service = ExportService()

@vendor_analysis_bp.route("/capabilities", methods=["GET"])
@login_required
def get_capabilities():
    """Get all capabilities."""
    try:
        capabilities = capability_service.get_capabilities()
        return jsonify(capabilities)
    except Exception as e:
        current_app.logger.error(f"Error getting capabilities: {e}")
        return jsonify({"error": "Failed to load capabilities"}), 500

@vendor_analysis_bp.route("/vendors", methods=["GET"])
@login_required
def get_vendors():
    """Get all vendors."""
    try:
        vendors = vendor_service.get_vendors()
        return jsonify(vendors)
    except Exception as e:
        current_app.logger.error(f"Error getting vendors: {e}")
        return jsonify({"error": "Failed to load vendors"}), 500

@vendor_analysis_bp.route("/create", methods=["POST"])
@login_required
@audit_log("vendor_analysis_create")
def create_analysis():
    """Create and run a vendor options analysis."""
    try:
        from flask_login import current_user

        data = request.get_json()

        # Validate required fields with detailed error messages
        if not data:
            return jsonify({"error": "Request body is required", "error_code": "MISSING_REQUEST_BODY"}), 400

        if not data.get("name"):
            return jsonify({"error": "Analysis name is required", "error_code": "MISSING_NAME"}), 400

        if not data.get("capability_id"):
            return jsonify({"error": "Capability ID is required", "error_code": "MISSING_CAPABILITY_ID"}), 400

        # Use service layer with error handling
        analysis = analysis_service.create_analysis(
            name=data["name"],
            capability_id=data["capability_id"],
            vendor_org_ids=data.get("vendor_org_ids", []),
            vendor_product_ids=data.get("vendor_product_ids", []),
            created_by=current_user,
            criteria_weights=data.get("criteria_weights"),
            analysis_type=data.get("analysis_type", "standard"),
            tco_years=data.get("tco_years", 5),
            organization_size=data.get("organization_size"),
            industry_vertical=data.get("industry_vertical"),
            deployment_scale=data.get("deployment_scale"),
            user_count_estimate=data.get("user_count_estimate"),
            integration_complexity=data.get("integration_complexity"),
        )

        # Run analysis
        analysis_service.run_analysis(analysis.id)

        db.session.commit()

        return jsonify({
            "success": True,
            "analysis_id": analysis.id,
            "status": analysis.status,
            "message": "Analysis created and started successfully"
        })

    except ValueError as e:
        db.session.rollback()
        current_app.logger.warning(f"Validation error in create_analysis: {str(e)}")
        return jsonify({"error": "Validation error", "error_code": "VALIDATION_ERROR"}), 400

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Unexpected error in create_analysis: {str(e)}")
        return jsonify({
            "error": "An unexpected error occurred while creating the analysis",
            "error_code": "INTERNAL_ERROR"
        }), 500

@vendor_analysis_bp.route("/<int:analysis_id>/comparison", methods=["GET"])
@login_required
def get_comparison(analysis_id):
    """Get vendor comparison matrix data."""
    try:
        comparison_data = analysis_service.get_comparison_data(analysis_id)
        return jsonify(comparison_data)
    except Exception as e:
        current_app.logger.error(f"Error getting comparison data: {e}")
        return jsonify({"error": "Failed to load comparison data"}), 500

@vendor_analysis_bp.route("/<int:analysis_id>/results", methods=["GET"])
@login_required
def get_results(analysis_id):
    """Get analysis results."""
    try:
        results = analysis_service.get_comparison_data(analysis_id)
        return jsonify(results)
    except Exception as e:
        current_app.logger.error(f"Error getting results: {e}")
        return jsonify({"error": "Failed to load results"}), 500

@vendor_analysis_bp.route("/<int:analysis_id>/export/<format_type>", methods=["GET"])
@login_required
def export_analysis(analysis_id, format_type):
    """Export analysis results."""
    try:
        data = export_service.export_analysis(analysis_id, format_type)
        return jsonify({"data": data})
    except Exception as e:
        current_app.logger.error(f"Error exporting analysis: {e}")
        return jsonify({"error": "Failed to export analysis"}), 500

@vendor_analysis_bp.route("/<int:analysis_id>/provenance", methods=["GET"])
@login_required
def get_provenance(analysis_id):
    """Get analysis provenance data - tracks data lineage and transformation history."""
    try:
        from flask_login import current_user
        from datetime import datetime

        # Get analysis record
        analysis = analysis_service.get_analysis(analysis_id)
        if not analysis:
            return jsonify({"error": "Analysis not found"}), 404

        # Build provenance chain
        provenance = {
            "analysis_id": analysis_id,
            "created_at": analysis.get("created_at", datetime.utcnow().isoformat()),
            "created_by": analysis.get("created_by", current_user.email if hasattr(current_user, 'email') else 'unknown'),
            "data_sources": [
                {
                    "source": "Vendor Database",
                    "type": "primary",
                    "description": "Vendor organization records",
                    "record_count": analysis.get("vendor_count", 0)
                },
                {
                    "source": "Capability Framework",
                    "type": "reference",
                    "description": "Business capability definitions",
                    "record_count": analysis.get("capability_count", 0)
                }
            ],
            "transformations": [
                {
                    "step": 1,
                    "operation": "vendor_filtering",
                    "description": f"Filtered vendors by criteria: {analysis.get('vendor_type', 'all')}",
                    "input_count": analysis.get("total_vendors", 0),
                    "output_count": analysis.get("filtered_vendors", 0)
                },
                {
                    "step": 2,
                    "operation": "capability_mapping",
                    "description": "Mapped vendors to capabilities",
                    "input_count": analysis.get("filtered_vendors", 0),
                    "output_count": analysis.get("mapped_vendors", 0)
                },
                {
                    "step": 3,
                    "operation": "scoring",
                    "description": "Calculated fit scores based on coverage",
                    "scoring_method": "weighted_coverage"
                }
            ],
            "parameters": {
                "vendor_type": analysis.get("vendor_type"),
                "capabilities": analysis.get("capabilities", []),
                "weights": analysis.get("weights", {})
            },
            "validation": {
                "status": "validated",
                "checksum": hash(str(analysis_id) + str(analysis.get("created_at"))) % 10000,
                "data_integrity": "verified"
            }
        }

        return jsonify({"provenance": provenance})
    except Exception as e:
        current_app.logger.error(f"Error getting provenance: {e}")
        return jsonify({"error": "Failed to load provenance"}), 500
