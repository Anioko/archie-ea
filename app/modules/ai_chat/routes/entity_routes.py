"""
Entity matching, business output transformation, and architecture generation routes.

Routes:
- Business output: transform-output, available-roles, role-info, batch-transform
- Entity matching: entities/match, entities/types, entities/resolve,
  knowledge-graph/related, api/entities/match
- Architecture: architecture/generate, architecture/validate
"""

import logging

from flask import current_app, jsonify, request
from flask_login import login_required

from app.decorators import audit_log
from app.services.ai_architecture_service import CognitiveArchitectureService
from app.services.business_output_service import BusinessOutputService, StakeholderRole
from app.services.chat_entity_matching_service import ChatEntityMatchingService
from . import unified_ai_chat_bp

logger = logging.getLogger(__name__)

# ============================================================================
# BUSINESS OUTPUT TRANSFORMATION ROUTES
# ============================================================================


@unified_ai_chat_bp.route("/transform-output", methods=["POST"])
@login_required
@audit_log("ai_chat_transform_output")
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
        return jsonify(
            {"error": "Transformation failed", "details": "See server logs for details"}
        ), 500


@unified_ai_chat_bp.route("/available-roles", methods=["GET"])
@login_required
def get_available_roles():
    """Get list of available stakeholder roles."""
    try:
        service = BusinessOutputService()
        roles = service.get_available_roles()

        return jsonify({"success": True, "roles": roles})

    except Exception as e:
        return jsonify(
            {"error": "Failed to get roles", "details": "See server logs for details"}
        ), 500


@unified_ai_chat_bp.route("/role-info/<role_value>", methods=["GET"])
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
        return jsonify(
            {
                "error": "Failed to get role info",
                "details": "See server logs for details",
            }
        ), 500


@unified_ai_chat_bp.route("/batch-transform", methods=["POST"])
@login_required
@audit_log("ai_chat_batch_transform_outputs")
def batch_transform_outputs():
    """
    Transform multiple AI responses for different stakeholder roles.

    Expected JSON payload:
    {
        "transformations": [
            {
                "ai_response": {...},
                "role": "business_analyst"
            },
            {
                "ai_response": {...},
                "role": "executive"
            }
        ]
    }
    """
    try:
        data = request.get_json()
        if not data or "transformations" not in data:
            return jsonify({"error": "No transformations data received"}), 400

        transformations = data["transformations"]
        service = BusinessOutputService()
        results = []

        for transformation in transformations:
            ai_response = transformation.get("ai_response")
            role_value = transformation.get("role")

            if ai_response and role_value:
                try:
                    role = StakeholderRole(role_value)
                    transformed = service.transform_for_stakeholder(ai_response, role)
                    results.append(
                        {
                            "success": True,
                            "role": role_value,
                            "transformed_output": transformed,
                        }
                    )
                except ValueError:
                    results.append(
                        {
                            "success": False,
                            "role": role_value,
                            "error": f"Invalid role: {role_value}",
                        }
                    )
            else:
                results.append(
                    {
                        "success": False,
                        "role": role_value,
                        "error": "Missing ai_response or role",
                    }
                )

        return jsonify({"success": True, "results": results})

    except Exception as e:
        return jsonify(
            {
                "error": "Batch transformation failed",
                "details": "See server logs for details",
            }
        ), 500


# ============================================================================
# ENTITY MATCHING ROUTES
# ============================================================================


@unified_ai_chat_bp.route("/entities/match", methods=["POST"])
@login_required
@audit_log("ai_chat_match_entities")
def match_entities_ui():
    """Match entities based on input text using AI."""
    try:
        data = request.get_json()
        text = data.get("text", "")
        entity_types = data.get(
            "entity_types", []
        )  # Optional: limit to specific entity types
        context = data.get("context", {})  # Optional: additional context

        if not text:
            return jsonify({"error": "Text input is required"}), 400

        service = ChatEntityMatchingService()
        result = service.match_entities(text, entity_types, context)

        return jsonify(
            {
                "success": result.get("success", True),
                "matches": result.get("matches", []),
                "total": result.get("total", 0),
                "text_processed": text,
                "context_used": bool(context),
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error in match_entities_ui: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@unified_ai_chat_bp.route("/entities/types", methods=["GET"])
@login_required
def get_entity_types():
    """Get available entity types for matching."""
    try:
        service = ChatEntityMatchingService()
        entity_types = service.get_available_entity_types()

        return jsonify({"success": True, "entity_types": entity_types})

    except Exception as e:
        return jsonify(
            {
                "error": "Failed to get entity types",
                "details": "See server logs for details",
            }
        ), 500



# ============================================================================
# ARCHITECTURE GENERATION ROUTES
# ============================================================================


@unified_ai_chat_bp.route("/architecture/generate", methods=["POST"])
@login_required
@audit_log("ai_chat_generate_architecture")
def generate_architecture():
    """
    Generate ArchiMate architecture elements from natural language.

    Expected JSON payload:
    {
        "description": "Generate a business process for customer onboarding",
        "layer": "business",
        "element_type": "BusinessProcess",
        "context": {}
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        description = data.get("description")
        layer = data.get("layer", "business")
        element_type = data.get("element_type", "BusinessProcess")
        context = data.get("context", {})

        if not description:
            return jsonify({"error": "Description is required"}), 400

        service = CognitiveArchitectureService()
        result = service.generate_element(description, layer, element_type, context)

        return jsonify(
            {
                "success": True,
                "element": result.get("element"),
                "metadata": result.get("metadata", {}),
                "visualization": result.get("visualization", {}),
            }
        )

    except Exception as e:
        return jsonify(
            {
                "error": "Architecture generation failed",
                "details": "See server logs for details",
            }
        ), 500


@unified_ai_chat_bp.route("/architecture/validate", methods=["POST"])
@login_required
@audit_log("ai_chat_validate_architecture")
def validate_architecture():
    """
    Validate ArchiMate architecture elements.

    Expected JSON payload:
    {
        "elements": [...],
        "relationships": [...]
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        service = CognitiveArchitectureService()
        validation_result = service.validate_architecture(data)

        return jsonify(
            {
                "success": True,
                "is_valid": validation_result.get("is_valid", False),
                "issues": validation_result.get("issues", []),
                "recommendations": validation_result.get("recommendations", []),
            }
        )

    except Exception as e:
        return jsonify(
            {
                "error": "Architecture validation failed",
                "details": "See server logs for details",
            }
        ), 500



# ============================================================================
# ADDITIONAL ENTITY ROUTES
# ============================================================================


@unified_ai_chat_bp.route("/entities/resolve", methods=["POST"])
@login_required
@audit_log("ai_chat_resolve_entity")
def resolve_entity():
    """Resolve entity name (acronym expansion, normalization, etc.)."""
    try:
        from app.services.archimate.entity_resolution_service import (
            EntityResolutionService,
        )

        data = request.json
        entity_name = data.get("entity_name")
        entity_type = data.get("entity_type")
        context = data.get("context")

        if not entity_name:
            return jsonify({"success": False, "error": "Missing entity_name"}), 400

        resolver = EntityResolutionService()
        resolution = resolver.resolve_entity(entity_name, entity_type, context)

        return jsonify({"success": True, "resolution": resolution})

    except Exception as e:
        current_app.logger.error(f"Error resolving entity: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@unified_ai_chat_bp.route("/knowledge-graph/related", methods=["POST"])
@login_required
@audit_log("ai_chat_get_related_entities")
def get_related_entities():
    """Get related entities from knowledge graph."""
    try:
        from app.services.archimate.knowledge_graph_service import KnowledgeGraphService

        data = request.json
        element = data.get("element")

        if not element:
            return jsonify({"success": False, "error": "Missing element"}), 400

        kg_service = KnowledgeGraphService()
        related = kg_service.get_semantic_context(element, max_context=5)

        return jsonify({"success": True, "related_entities": related})

    except Exception as e:
        current_app.logger.error(f"Error getting related entities: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@unified_ai_chat_bp.route("/api/entities/match", methods=["POST"])
@login_required
@audit_log("ai_chat_match_entities_api")
def match_entities_api():
    """Match entities based on input text using chat-aware entity matching."""
    data = request.get_json() or {}
    text = data.get("text", "").strip()

    if not text:
        return jsonify({"success": False, "error": "Text is required"}), 400

    persona = data.get("persona", "enterprise_architect")
    domain = data.get("domain", "architecture")
    chat_history = data.get("chat_history")

    try:
        matcher = ChatEntityMatchingService()
        result = matcher.analyze_document_with_chat_context(
            document_text=text,
            user_persona=persona,
            domain=domain,
            chat_history=chat_history,
        )

        status_code = 200 if result.get("success") else 500
        return jsonify(result), status_code

    except Exception as e:
        current_app.logger.error(f"[AI_CHAT] Entity match error: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500

