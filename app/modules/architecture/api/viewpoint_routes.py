"""
DEPRECATED - Migrated to app/modules/architecture/api/viewpoint_routes.py
Set USE_NEW_ARCHITECTURE=true to use the new module instead. Remove after Phase 6 cleanup.

Original: ArchiMate Viewpoint API Routes
PRD - 010.2: API endpoints for viewpoint building and management

Provides REST API for:
- Building viewpoints from element selections
- Validating elements against viewpoint rules
- Listing available viewpoints
- Exporting viewpoints to SVG
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request
from flask_login import login_required
from app.config.archimate_viewpoints import (
    VIEWPOINT_CATEGORIES,
    VIEWPOINT_LAYERS,
    get_viewpoint,
    get_viewpoint_summary,
    get_viewpoints_for_layer,
    get_viewpoints_for_stakeholder,
)
from app.services.archimate.viewpoint_builder import (
    Viewpoint,
    get_viewpoint_builder,
)

logger = logging.getLogger(__name__)

# Create blueprint
viewpoint_bp = Blueprint("viewpoint_api", __name__, url_prefix="/api/viewpoints")


def handle_error(error: Exception, context: str) -> Dict[str, Any]:
    """Standard error handling for API endpoints"""
    logger.error(f"Error in {context}: {str(error)}")
    return {
        "error": str(error),
        "context": context,
        "timestamp": datetime.utcnow().isoformat(),
    }, 500


def validate_json_data(required_fields: List[str]) -> Optional[Dict[str, Any]]:
    """Validate JSON request data"""
    if not request.is_json:
        return {"error": "Request must be JSON"}, 400

    data = request.get_json()
    if not data:
        return {"error": "No data provided"}, 400

    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return {"error": f'Missing required fields: {", ".join(missing_fields)}'}, 400

    return None


# ==================== VIEWPOINT LISTING ====================


@viewpoint_bp.route("/", methods=["GET"])
@login_required
def list_viewpoints():
    """
    List All Available Viewpoints
    ---
    tags:
      - Viewpoints
    summary: Get all available ArchiMate viewpoints
    description: Returns a list of all 25 standard ArchiMate 3.2 viewpoints with their definitions
    parameters:
      - name: layer
        in: query
        type: string
        required: false
        description: Filter by layer (motivation, strategy, business, application, technology, physical, implementation, composite)
      - name: stakeholder
        in: query
        type: string
        required: false
        description: Filter by stakeholder role
      - name: category
        in: query
        type: string
        required: false
        description: Filter by category (basic, application, technology, etc.)
    responses:
      200:
        description: List of viewpoints
        schema:
          type: object
          properties:
            viewpoints:
              type: array
              items:
                type: object
            count:
              type: integer
    """
    try:
        builder = get_viewpoint_builder()

        layer = request.args.get("layer")
        stakeholder = request.args.get("stakeholder")
        category = request.args.get("category")

        viewpoints = builder.get_available_viewpoints()

        # Apply filters
        if layer:
            viewpoints = [vp for vp in viewpoints if vp["layer"].lower() == layer.lower()]

        if stakeholder:
            viewpoints = [
                vp
                for vp in viewpoints
                if any(stakeholder.lower() in s.lower() for s in vp["stakeholders"])
            ]

        if category and category in VIEWPOINT_CATEGORIES:
            category_codes = []
            for key in VIEWPOINT_CATEGORIES[category]:
                vp_def = get_viewpoint(key.upper()) or get_viewpoint(key)
                if vp_def:
                    category_codes.append(vp_def.code)
            viewpoints = [vp for vp in viewpoints if vp["code"] in category_codes]

        return jsonify(
            {
                "viewpoints": viewpoints,
                "count": len(viewpoints),
                "filters": {"layer": layer, "stakeholder": stakeholder, "category": category},
            }
        )

    except Exception as e:
        return handle_error(e, "list_viewpoints")


@viewpoint_bp.route("/categories", methods=["GET"])
@login_required
def get_viewpoint_categories():
    """
    Get Viewpoints by Category
    ---
    tags:
      - Viewpoints
    summary: Get viewpoints organized by category
    description: Returns viewpoints grouped by their functional category
    responses:
      200:
        description: Viewpoints by category
    """
    try:
        builder = get_viewpoint_builder()
        categories = builder.get_viewpoints_by_category()

        return jsonify(
            {"categories": categories, "category_names": list(VIEWPOINT_CATEGORIES.keys())}
        )

    except Exception as e:
        return handle_error(e, "get_viewpoint_categories")


@viewpoint_bp.route("/layers", methods=["GET"])
@login_required
def get_viewpoint_layers():
    """
    Get Available Layers
    ---
    tags:
      - Viewpoints
    summary: Get list of ArchiMate layers
    description: Returns list of layers and viewpoints for each layer
    responses:
      200:
        description: Layers with viewpoints
    """
    try:
        result = {}
        for layer in VIEWPOINT_LAYERS:
            layer_viewpoints = get_viewpoints_for_layer(layer)
            result[layer] = [
                {"code": vp.code, "name": vp.name, "purpose": vp.purpose} for vp in layer_viewpoints
            ]

        return jsonify({"layers": result, "layer_order": VIEWPOINT_LAYERS})

    except Exception as e:
        return handle_error(e, "get_viewpoint_layers")


@viewpoint_bp.route("/<viewpoint_code>", methods=["GET"])
@login_required
def get_viewpoint_detail(viewpoint_code: str):
    """
    Get Viewpoint Details
    ---
    tags:
      - Viewpoints
    summary: Get detailed information about a specific viewpoint
    description: Returns full definition of a viewpoint including allowed elements and relationships
    parameters:
      - name: viewpoint_code
        in: path
        type: string
        required: true
        description: Viewpoint code (e.g., 'APC', 'ORG', 'LAY')
    responses:
      200:
        description: Viewpoint details
      404:
        description: Viewpoint not found
    """
    try:
        vp_def = get_viewpoint(viewpoint_code)

        if not vp_def:
            return (
                jsonify(
                    {
                        "error": f"Viewpoint '{viewpoint_code}' not found",
                        "available_codes": list(get_viewpoint_summary().keys()),
                    }
                ),
                404,
            )

        return jsonify(
            {
                "viewpoint": {
                    "code": vp_def.code,
                    "name": vp_def.name,
                    "purpose": vp_def.purpose,
                    "layer": vp_def.layer,
                    "typical_stakeholders": vp_def.typical_stakeholders,
                    "allowed_elements": vp_def.allowed_elements,
                    "allowed_relationships": vp_def.allowed_relationships,
                    "concerns": vp_def.concerns,
                }
            }
        )

    except Exception as e:
        return handle_error(e, "get_viewpoint_detail")


# ==================== VIEWPOINT BUILDING ====================


@viewpoint_bp.route("/build", methods=["POST"])
@login_required
def build_viewpoint():
    """
    Build Viewpoint from Elements
    ---
    tags:
      - Viewpoints
    summary: Build a viewpoint from selected elements
    description: Creates a viewpoint view from element selection with auto-layout and filtering
    security:
      - cookieAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - viewpoint_code
          properties:
            viewpoint_code:
              type: string
              description: Viewpoint code (e.g., 'APC', 'ORG')
            element_ids:
              type: array
              items:
                type: integer
              description: List of element IDs to include (optional, auto-selects if omitted)
            architecture_id:
              type: integer
              description: Filter by architecture model ID
            include_relationships:
              type: boolean
              default: true
              description: Include relationships between elements
            auto_layout:
              type: boolean
              default: true
              description: Automatically position elements
            max_elements:
              type: integer
              default: 100
              description: Maximum number of elements to include
    responses:
      200:
        description: Built viewpoint
      400:
        description: Validation error
      401:
        description: Unauthorized
    """
    try:
        validation_error = validate_json_data(["viewpoint_code"])
        if validation_error:
            return validation_error

        data = request.get_json()
        builder = get_viewpoint_builder()

        viewpoint = builder.build_viewpoint(
            viewpoint_code=data["viewpoint_code"],
            element_ids=data.get("element_ids"),
            architecture_id=data.get("architecture_id"),
            include_relationships=data.get("include_relationships", True),
            auto_layout=data.get("auto_layout", True),
            max_elements=data.get("max_elements", 100),
        )

        return jsonify(
            {
                "viewpoint": viewpoint.to_dict(),
                "message": f"Viewpoint '{viewpoint.name}' built successfully",
            }
        )

    except ValueError as e:
        return jsonify({"error": "Invalid request parameters"}), 400
    except Exception as e:
        return handle_error(e, "build_viewpoint")


@viewpoint_bp.route("/build/<viewpoint_code>", methods=["GET"])
@login_required
def build_viewpoint_get(viewpoint_code: str):
    """
    Build Viewpoint (GET Method)
    ---
    tags:
      - Viewpoints
    summary: Build a viewpoint with query parameters
    description: Alternative GET endpoint for building viewpoints
    security:
      - cookieAuth: []
    parameters:
      - name: viewpoint_code
        in: path
        type: string
        required: true
        description: Viewpoint code
      - name: architecture_id
        in: query
        type: integer
        required: false
        description: Architecture model ID
      - name: max_elements
        in: query
        type: integer
        default: 50
        description: Maximum elements
    responses:
      200:
        description: Built viewpoint
      401:
        description: Unauthorized
    """
    try:
        builder = get_viewpoint_builder()

        architecture_id = request.args.get("architecture_id", type=int)
        max_elements = request.args.get("max_elements", 50, type=int)

        viewpoint = builder.build_viewpoint(
            viewpoint_code=viewpoint_code,
            architecture_id=architecture_id,
            max_elements=max_elements,
        )

        return jsonify({"viewpoint": viewpoint.to_dict()})

    except ValueError as e:
        return jsonify({"error": "Invalid request parameters"}), 400
    except Exception as e:
        return handle_error(e, "build_viewpoint_get")


# ==================== VIEWPOINT VALIDATION ====================


@viewpoint_bp.route("/validate", methods=["POST"])
@login_required
def validate_viewpoint():
    """
    Validate Elements Against Viewpoint
    ---
    tags:
      - Viewpoints
    summary: Validate elements and relationships against viewpoint rules
    description: Checks if elements and relationships are allowed in a viewpoint
    security:
      - cookieAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - viewpoint_code
            - element_ids
          properties:
            viewpoint_code:
              type: string
              description: Viewpoint code to validate against
            element_ids:
              type: array
              items:
                type: integer
              description: List of element IDs to validate
            relationship_ids:
              type: array
              items:
                type: integer
              description: Optional list of relationship IDs to validate
    responses:
      200:
        description: Validation result
      400:
        description: Validation error
      401:
        description: Unauthorized
    """
    try:
        validation_error = validate_json_data(["viewpoint_code", "element_ids"])
        if validation_error:
            return validation_error

        data = request.get_json()
        builder = get_viewpoint_builder()

        result = builder.validate_viewpoint(
            viewpoint_code=data["viewpoint_code"],
            element_ids=data["element_ids"],
            relationship_ids=data.get("relationship_ids"),
        )

        return jsonify({"validation": result.to_dict(), "viewpoint_code": data["viewpoint_code"]})

    except Exception as e:
        return handle_error(e, "validate_viewpoint")


# ==================== VIEWPOINT SUGGESTIONS ====================


@viewpoint_bp.route("/suggest", methods=["POST"])
@login_required
def suggest_viewpoints():
    """
    Suggest Appropriate Viewpoints
    ---
    tags:
      - Viewpoints
    summary: Get viewpoint suggestions based on elements or stakeholder
    description: Analyzes elements or stakeholder role to suggest appropriate viewpoints
    security:
      - cookieAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            element_ids:
              type: array
              items:
                type: integer
              description: List of element IDs to analyze
            stakeholder_role:
              type: string
              description: Stakeholder role (e.g., 'Enterprise Architect')
            concerns:
              type: array
              items:
                type: string
              description: List of concerns to address
    responses:
      200:
        description: Suggested viewpoints
      401:
        description: Unauthorized
    """
    try:
        data = request.get_json() or {}
        builder = get_viewpoint_builder()

        suggestions = builder.suggest_viewpoints(
            element_ids=data.get("element_ids"),
            stakeholder_role=data.get("stakeholder_role"),
            concerns=data.get("concerns"),
        )

        return jsonify(
            {
                "suggestions": suggestions,
                "count": len(suggestions),
                "criteria": {
                    "element_ids": data.get("element_ids"),
                    "stakeholder_role": data.get("stakeholder_role"),
                    "concerns": data.get("concerns"),
                },
            }
        )

    except Exception as e:
        return handle_error(e, "suggest_viewpoints")


@viewpoint_bp.route("/suggest/stakeholder/<stakeholder_role>", methods=["GET"])
@login_required
def suggest_for_stakeholder(stakeholder_role: str):
    """
    Suggest Viewpoints for Stakeholder
    ---
    tags:
      - Viewpoints
    summary: Get viewpoint suggestions for a stakeholder role
    description: Returns viewpoints relevant for a specific stakeholder role
    parameters:
      - name: stakeholder_role
        in: path
        type: string
        required: true
        description: Stakeholder role (e.g., 'Enterprise Architect', 'CIO')
    responses:
      200:
        description: Suggested viewpoints
    """
    try:
        viewpoints = get_viewpoints_for_stakeholder(stakeholder_role)

        return jsonify(
            {
                "suggestions": [
                    {
                        "code": vp.code,
                        "name": vp.name,
                        "purpose": vp.purpose,
                        "layer": vp.layer,
                        "concerns": vp.concerns,
                    }
                    for vp in viewpoints
                ],
                "stakeholder_role": stakeholder_role,
                "count": len(viewpoints),
            }
        )

    except Exception as e:
        return handle_error(e, "suggest_for_stakeholder")


# ==================== VIEWPOINT EXPORT ====================


@viewpoint_bp.route("/export/svg", methods=["POST"])
@login_required
def export_viewpoint_svg():
    """
    Export Viewpoint to SVG
    ---
    tags:
      - Viewpoints
    summary: Export a viewpoint to SVG format
    description: Generates an SVG visualization of the viewpoint
    security:
      - cookieAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - viewpoint_code
          properties:
            viewpoint_code:
              type: string
              description: Viewpoint code
            element_ids:
              type: array
              items:
                type: integer
              description: List of element IDs
            architecture_id:
              type: integer
              description: Architecture model ID
    responses:
      200:
        description: SVG content
        content:
          image/svg+xml:
            schema:
              type: string
      400:
        description: Validation error
      401:
        description: Unauthorized
    """
    try:
        validation_error = validate_json_data(["viewpoint_code"])
        if validation_error:
            return validation_error

        data = request.get_json()
        builder = get_viewpoint_builder()

        # Build the viewpoint
        viewpoint = builder.build_viewpoint(
            viewpoint_code=data["viewpoint_code"],
            element_ids=data.get("element_ids"),
            architecture_id=data.get("architecture_id"),
        )

        # Export to SVG
        svg_content = builder.export_to_svg(viewpoint)

        # Return as SVG with appropriate content type
        from flask import Response

        return Response(
            svg_content,
            mimetype="image/svg+xml",
            headers={"Content-Disposition": f"attachment; filename=viewpoint_{viewpoint.code}.svg"},
        )

    except ValueError as e:
        return jsonify({"error": "Invalid request parameters"}), 400
    except Exception as e:
        return handle_error(e, "export_viewpoint_svg")


@viewpoint_bp.route("/export/json", methods=["POST"])
@login_required
def export_viewpoint_json():
    """
    Export Viewpoint to JSON
    ---
    tags:
      - Viewpoints
    summary: Export a viewpoint to JSON format
    description: Generates a JSON export of the viewpoint for external tools
    security:
      - cookieAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - viewpoint_code
          properties:
            viewpoint_code:
              type: string
            element_ids:
              type: array
              items:
                type: integer
            architecture_id:
              type: integer
    responses:
      200:
        description: JSON export
      400:
        description: Validation error
      401:
        description: Unauthorized
    """
    try:
        validation_error = validate_json_data(["viewpoint_code"])
        if validation_error:
            return validation_error

        data = request.get_json()
        builder = get_viewpoint_builder()

        viewpoint = builder.build_viewpoint(
            viewpoint_code=data["viewpoint_code"],
            element_ids=data.get("element_ids"),
            architecture_id=data.get("architecture_id"),
        )

        return jsonify(
            {
                "export": viewpoint.to_dict(),
                "format": "json",
                "exported_at": datetime.utcnow().isoformat(),
            }
        )

    except ValueError as e:
        return jsonify({"error": "Invalid request parameters"}), 400
    except Exception as e:
        return handle_error(e, "export_viewpoint_json")


# ==================== VIEWPOINT SUMMARY ====================


@viewpoint_bp.route("/summary", methods=["GET"])
@login_required
def get_summary():
    """
    Get Viewpoint Summary
    ---
    tags:
      - Viewpoints
    summary: Get summary statistics for all viewpoints
    description: Returns summary information about all viewpoints
    responses:
      200:
        description: Viewpoint summary
    """
    try:
        summary = get_viewpoint_summary()

        # Calculate totals
        total_viewpoints = len(summary)
        layers = {}
        for code, info in summary.items():
            layer = info["layer"]
            if layer not in layers:
                layers[layer] = 0
            layers[layer] += 1

        return jsonify(
            {
                "summary": summary,
                "statistics": {
                    "total_viewpoints": total_viewpoints,
                    "by_layer": layers,
                    "available_layers": VIEWPOINT_LAYERS,
                    "available_categories": list(VIEWPOINT_CATEGORIES.keys()),
                },
            }
        )

    except Exception as e:
        return handle_error(e, "get_summary")


# Blueprint registration helper
def register_viewpoint_api(app):
    """Register the viewpoint API blueprint"""
    app.register_blueprint(viewpoint_bp)
    return app
