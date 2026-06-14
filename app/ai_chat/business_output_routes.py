"""
Business Output Routes - Stakeholder-Specific AI Response Transformation
API endpoints for transforming AI chat outputs into business-friendly insights
"""

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.services.business_output_service import BusinessOutputService, StakeholderRole

business_output_bp = Blueprint("business_output", __name__)


@business_output_bp.route("/transform-output", methods=["POST"])
@login_required
def transform_output():
    """
    Transform AI chat response for specific stakeholder role.

    Expected JSON payload:
    {
        "ai_response": {
            "response": "AI response text",
            "domain": "domain_name",
            "metadata": {}
        },
        "role": "business_analyst"  # or other stakeholder role
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        ai_response = data.get("ai_response")
        role_value = data.get("role")

        if not ai_response:
            return jsonify({"error": "AI response is required"}), 400

        if not role_value:
            return jsonify({"error": "Stakeholder role is required"}), 400

        # Validate role
        try:
            role = StakeholderRole(role_value)
        except ValueError:
            return jsonify({"error": f"Invalid role: {role_value}"}), 400

        # Transform response
        service = BusinessOutputService()
        transformed = service.transform_for_stakeholder(ai_response, role)

        return jsonify({"success": True, "transformed_output": transformed})

    except Exception as e:
        return jsonify({"error": "Transformation failed"}), 500


@business_output_bp.route("/available-roles", methods=["GET"])
@login_required
def get_available_roles():
    """Get list of available stakeholder roles."""
    try:
        service = BusinessOutputService()
        roles = service.get_available_roles()

        return jsonify({"success": True, "roles": roles})

    except Exception as e:
        return jsonify({"error": "Failed to get roles"}), 500


@business_output_bp.route("/role-info/<role_value>", methods=["GET"])
@login_required
def get_role_info(role_value):
    """Get detailed information about a specific role."""
    try:
        # Validate role
        try:
            role = StakeholderRole(role_value)
        except ValueError:
            return jsonify({"error": f"Invalid role: {role_value}"}), 400

        service = BusinessOutputService()
        roles = service.get_available_roles()

        # Find the specific role
        role_info = next((r for r in roles if r["value"] == role_value), None)

        if not role_info:
            return jsonify({"error": "Role not found"}), 404

        return jsonify({"success": True, "role_info": role_info})

    except Exception as e:
        return jsonify({"error": "Failed to get role info"}), 500
