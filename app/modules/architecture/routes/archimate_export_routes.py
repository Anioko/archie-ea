"""
DEPRECATED: This file is migrated to app/modules/architecture/.
Registration is now centralized via app.modules.architecture.register().
Do NOT modify -- kept as fallback until Phase 6 cleanup.

ArchiMate Viewpoint Export API Routes

Provides REST API endpoints for generating ArchiMate viewpoints
and exporting to Open Exchange format.

Endpoints:
- GET /api/archimate-export/viewpoints - List available viewpoints
- GET /api/archimate-export/application-cooperation - Generate Application Cooperation viewpoint
- GET /api/archimate-export/service-realization - Generate Service Realization viewpoint
- GET /api/archimate-export/technology-usage - Generate Technology Usage viewpoint
- GET /api/archimate-export/capability-map - Generate Capability Map viewpoint
- GET /api/archimate-export/layered/<capability_id> - Generate Layered viewpoint
- GET /api/archimate-export/export/<viewpoint_type> - Export to Open Exchange XML
"""

from flask import Blueprint, Response, current_app, jsonify, request
from flask_login import login_required

from app.services.archimate_viewpoint_generator import ArchiMateViewpointGenerator

archimate_export_bp = Blueprint("archimate_export", __name__, url_prefix="/api/archimate-export")


@archimate_export_bp.route("/viewpoints", methods=["GET"])
@login_required
def list_viewpoints():
    """
    List available ArchiMate viewpoint types.

    Returns:
        JSON list of available viewpoints with descriptions
    """
    try:
        service = ArchiMateViewpointGenerator()
        viewpoints = service.get_available_viewpoints()

        return jsonify({"success": True, "data": viewpoints})
    except Exception as e:
        current_app.logger.error(f"Error listing viewpoints: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@archimate_export_bp.route("/application-cooperation", methods=["GET"])
@login_required
def generate_application_cooperation():
    """
    Generate Application Cooperation viewpoint.

    Query Parameters:
        domain_id (int): Optional domain ID to filter applications
        capability_ids (str): Comma-separated capability IDs to filter
        include_data_flows (bool): Include data flow relationships (default: true)

    Returns:
        JSON containing viewpoint elements and relationships
    """
    domain_id = request.args.get("domain_id", type=int)
    capability_ids_str = request.args.get("capability_ids", "")
    include_data_flows = request.args.get("include_data_flows", "true").lower() == "true"

    capability_ids = None
    if capability_ids_str:
        try:
            capability_ids = [int(x.strip()) for x in capability_ids_str.split(",")]
        except ValueError:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Invalid capability_ids format. Use comma-separated integers.",
                    }
                ),
                400,
            )

    try:
        service = ArchiMateViewpointGenerator()
        viewpoint = service.generate_application_cooperation_viewpoint(
            domain_id=domain_id,
            capability_ids=capability_ids,
            include_data_flows=include_data_flows,
        )

        return jsonify({"success": True, "data": viewpoint})
    except Exception as e:
        current_app.logger.error(f"Error generating application cooperation viewpoint: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@archimate_export_bp.route("/service-realization", methods=["GET"])
@login_required
def generate_service_realization():
    """
    Generate Service Realization viewpoint.

    Query Parameters:
        capability_id (int): Optional capability ID to focus on

    Returns:
        JSON containing viewpoint elements and relationships
    """
    capability_id = request.args.get("capability_id", type=int)

    try:
        service = ArchiMateViewpointGenerator()
        viewpoint = service.generate_service_realization_viewpoint(capability_id=capability_id)

        return jsonify({"success": True, "data": viewpoint})
    except Exception as e:
        current_app.logger.error(f"Error generating service realization viewpoint: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@archimate_export_bp.route("/technology-usage", methods=["GET"])
@login_required
def generate_technology_usage():
    """
    Generate Technology Usage viewpoint.

    Query Parameters:
        application_ids (str): Comma-separated application IDs to include

    Returns:
        JSON containing viewpoint elements and relationships
    """
    app_ids_str = request.args.get("application_ids", "")

    application_ids = None
    if app_ids_str:
        try:
            application_ids = [int(x.strip()) for x in app_ids_str.split(",")]
        except ValueError:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Invalid application_ids format. Use comma-separated integers.",
                    }
                ),
                400,
            )

    try:
        service = ArchiMateViewpointGenerator()
        viewpoint = service.generate_technology_usage_viewpoint(application_ids=application_ids)

        return jsonify({"success": True, "data": viewpoint})
    except Exception as e:
        current_app.logger.error(f"Error generating technology usage viewpoint: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@archimate_export_bp.route("/capability-map", methods=["GET"])
@login_required
def generate_capability_map():
    """
    Generate Capability Map viewpoint.

    Query Parameters:
        domain_id (int): Optional domain ID to filter
        level (int): Optional capability level (1, 2, or 3)

    Returns:
        JSON containing capability hierarchy with application support
    """
    domain_id = request.args.get("domain_id", type=int)
    level = request.args.get("level", type=int)

    if level is not None and level not in [1, 2, 3]:
        return jsonify({"success": False, "error": "Level must be 1, 2, or 3"}), 400

    try:
        service = ArchiMateViewpointGenerator()
        viewpoint = service.generate_capability_map_viewpoint(domain_id=domain_id, level=level)

        return jsonify({"success": True, "data": viewpoint})
    except Exception as e:
        current_app.logger.error(f"Error generating capability map viewpoint: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@archimate_export_bp.route("/layered/<int:capability_id>", methods=["GET"])
@login_required
def generate_layered(capability_id: int):
    """
    Generate Layered viewpoint centered on a capability.

    Path Parameters:
        capability_id: Capability ID to center the view on

    Returns:
        JSON containing cross-layer view from capability to technology
    """
    try:
        service = ArchiMateViewpointGenerator()
        viewpoint = service.generate_layered_viewpoint(capability_id=capability_id)

        if "error" in viewpoint:
            return jsonify({"success": False, "error": viewpoint["error"]}), 404

        return jsonify({"success": True, "data": viewpoint})
    except Exception as e:
        current_app.logger.error(f"Error generating layered viewpoint: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@archimate_export_bp.route("/export/<viewpoint_type>", methods=["GET"])
@login_required
def export_viewpoint(viewpoint_type: str):
    """
    Export viewpoint to ArchiMate Open Exchange XML format.

    Path Parameters:
        viewpoint_type: Type of viewpoint (application-cooperation, service-realization,
                        technology-usage, capability-map)

    Query Parameters:
        Various parameters depending on viewpoint type
        format (str): Export format - 'xml' only for now (default: xml)

    Returns:
        ArchiMate Open Exchange XML file
    """
    valid_types = [
        "application-cooperation",
        "service-realization",
        "technology-usage",
        "capability-map",
    ]
    if viewpoint_type not in valid_types:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Invalid viewpoint type. Must be one of: {valid_types}",
                }
            ),
            400,
        )

    try:
        service = ArchiMateViewpointGenerator()

        # Generate the appropriate viewpoint
        if viewpoint_type == "application-cooperation":
            viewpoint = service.generate_application_cooperation_viewpoint()
        elif viewpoint_type == "service-realization":
            capability_id = request.args.get("capability_id", type=int)
            viewpoint = service.generate_service_realization_viewpoint(capability_id=capability_id)
        elif viewpoint_type == "technology-usage":
            viewpoint = service.generate_technology_usage_viewpoint()
        elif viewpoint_type == "capability-map":
            domain_id = request.args.get("domain_id", type=int)
            viewpoint = service.generate_capability_map_viewpoint(domain_id=domain_id)

        # Export to XML (returns _ValidatedXML with validation_errors attribute)
        xml_content = service.export_to_open_exchange(viewpoint)

        headers = {
            "Content-Disposition": f"attachment; filename=archimate_{viewpoint_type}.xml",
        }
        validation_errors = getattr(xml_content, "validation_errors", [])
        headers["X-Validation-Errors"] = str(len(validation_errors))

        return Response(
            str(xml_content),
            mimetype="application/xml",
            headers=headers,
        )
    except Exception as e:
        current_app.logger.error(f"Error exporting viewpoint: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@archimate_export_bp.route("/health", methods=["GET"])
@login_required
def health_check():
    """
    Health check endpoint for the ArchiMate Export service.

    Returns:
        JSON with service status
    """
    return jsonify(
        {
            "success": True,
            "service": "archimate-export",
            "status": "healthy",
            "endpoints": [
                "GET /api/archimate-export/viewpoints",
                "GET /api/archimate-export/application-cooperation",
                "GET /api/archimate-export/service-realization",
                "GET /api/archimate-export/technology-usage",
                "GET /api/archimate-export/capability-map",
                "GET /api/archimate-export/layered/<capability_id>",
                "GET /api/archimate-export/export/<viewpoint_type>",
            ],
        }
    )
