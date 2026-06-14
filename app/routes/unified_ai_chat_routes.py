"""
Unified AI Chat Routes

Consolidates all AI chat functionality from:
- ai_chat/routes.py (main chat interface)
- ai_chat/data_interaction_routes.py (AI data modifications)
- ai_chat/business_output_routes.py (stakeholder transformations)
- ai_chat/entity_matching_routes.py (entity matching)

Total: 4 blueprints consolidated into one comprehensive AI chat system.
"""

import json
import os
import time
from datetime import datetime
from enum import Enum  # dead-code-ok: reserved for future role enum extension

from flask import (  # dead-code-ok: flash/Enum reserved; blueprint aggregates many routes
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.inspection import inspect

from app import db
from app.models.ai_service import AIPromptTemplate
from app.models.application_portfolio import ApplicationComponent
from app.models.business_capabilities import BusinessCapability
from app.models.unified_capability import UnifiedCapability
from app.models.vendor.vendor_organization import VendorOrganization
from app.services.ai_architecture_service import CognitiveArchitectureService
from app.services.ai_data_interaction_service import AIDataInteractionService
from app.services.business_output_service import BusinessOutputService, StakeholderRole
from app.services.chat_entity_matching_service import ChatEntityMatchingService
from app.services.llm_service import LLMService
from app.services.multi_domain_chat_service import MultiDomainChatService

# Create unified AI chat blueprint
unified_ai_chat_bp = Blueprint("unified_ai_chat", __name__, url_prefix="/ai-chat")

# ============================================================================
# MULTI-DOMAIN CHAT SERVICE
# ============================================================================


def get_chat_service():
    """Get multi-domain chat service instance"""
    try:
        user_id = None
        if (
            current_user
            and hasattr(current_user, "is_authenticated")
            and current_user.is_authenticated
        ):
            user_id = current_user.id
        return MultiDomainChatService(user_id=user_id)
    except Exception as e:
        current_app.logger.error(f"Error creating chat service: {e}")
        # Return a basic service instance for unauthenticated users
        return MultiDomainChatService(user_id=None)


# ENT-041: role-aware in-memory rate limiter (requests per window).
# Keyed by (user_id, window_bucket). Counts requests in the current window.
_RATE_WINDOW_SEC = 3600  # fabricated-values-ok: named constant for rate limit window in seconds
_RATE_LIMITS_BY_ROLE = {
    "admin": 200,
    "architect": 120,
    "analyst": 60,
    "default": 30,
}
_rate_limit_store: dict = {}  # {(user_id, window): count}


def _get_role_rate_limit(user) -> int:
    """Return the hourly request ceiling for the given user's role (ENT-041)."""
    if not user or not hasattr(user, "is_authenticated") or not user.is_authenticated:
        return _RATE_LIMITS_BY_ROLE["default"]
    role = getattr(user, "role", "default") or "default"
    return _RATE_LIMITS_BY_ROLE.get(str(role).lower(), _RATE_LIMITS_BY_ROLE["default"])


def _check_rate_limit(user_id: int, limit: int) -> bool:
    """Return True if the request is within the rate limit, False if exceeded (ENT-041)."""
    window = int(time.time() // _RATE_WINDOW_SEC)
    key = (user_id, window)
    count = _rate_limit_store.get(key, 0)
    if count >= limit:
        return False
    _rate_limit_store[key] = count + 1
    return True


# ============================================================================
# MAIN CHAT INTERFACE ROUTES
# ============================================================================


@unified_ai_chat_bp.route("/", strict_slashes=False)
@unified_ai_chat_bp.route("", strict_slashes=False)
@login_required
def index():
    """Renders the Enhanced Multi-Domain AI Chat Interface."""
    # Pre-fetch prompt templates for the UI selector
    try:
        templates = AIPromptTemplate.query.limit(200).all()
    except Exception as e:
        current_app.logger.warning(f"Could not load prompt templates: {e}")
        templates = []

    # Get multi-domain service and configurations
    chat_service = get_chat_service()
    domain_config = chat_service.get_available_domains()
    persona_config = chat_service.get_available_personas()

    # Get context data for different domains (configurable limit)
    # Wrapped in try/except to handle model configuration issues gracefully
    context_limit = current_app.config.get("AI_CHAT_CONTEXT_LIMIT", 50)
    context_data = {
        "applications": [],
        "capabilities": [],
        "vendors": [],
        "unified_capabilities": [],
    }

    try:
        context_data["applications"] = ApplicationComponent.query.limit(context_limit).all()
    except Exception as e:
        current_app.logger.warning(f"Could not load applications: {e}")

    try:
        context_data["capabilities"] = BusinessCapability.query.limit(context_limit).all()
    except Exception as e:
        current_app.logger.warning(f"Could not load capabilities: {e}")

    try:
        context_data["vendors"] = VendorOrganization.query.limit(context_limit).all()
    except Exception as e:
        current_app.logger.warning(f"Could not load vendors: {e}")

    try:
        context_data["unified_capabilities"] = UnifiedCapability.query.limit(context_limit).all()
    except Exception as e:
        current_app.logger.warning(f"Could not load unified capabilities: {e}")

    return render_template(
        "ai_chat/index.html",
        prompt_templates=templates,
        domain_config=domain_config,
        persona_config=persona_config,
        context_data=context_data,
    )


@unified_ai_chat_bp.route("/document-upload")
@login_required
def document_upload_view():
    """Upload lives INSIDE the chat (floating panel); the standalone page was a
    blank macro-only render (UIQA-004). Redirect with the panel auto-opened."""
    from flask import redirect, url_for
    return redirect(url_for("unified_ai_chat.index", panel="docs"))


@unified_ai_chat_bp.route("/business-output")
@login_required
def business_output_view():
    """Stakeholder-output transformation happens in-chat; the standalone page was
    an empty stub (UIQA-004). Redirect into the chat."""
    from flask import redirect, url_for
    return redirect(url_for("unified_ai_chat.index"))


@unified_ai_chat_bp.route("/entity-matching")
@login_required
def entity_matching_view():
    """Renders the Entity Matching interface for AI-powered entity resolution."""
    return render_template("ai_chat/entity_matching_chat_interface.html")


@unified_ai_chat_bp.route("/models", methods=["GET"])
@login_required
def get_available_models():
    """
    Get available AI models
    ---
    tags:
      - AI Chat
    summary: List available LLM models
    description: Get all available LLM models configured and enabled in the system
    responses:
      200:
        description: Available models list
        schema:
          type: object
          properties:
            success:
              type: boolean
            models:
              type: array
              items:
                type: object
                properties:
                  provider:
                    type: string
                  model:
                    type: string
                  display_name:
                    type: string
                  recommended_for:
                    type: array
                    items:
                      type: string
            current_provider:
              type: string
            current_model:
              type: string
    """
    try:
        from app.models.models import APISettings

        # Get all enabled providers
        enabled_providers = APISettings.query.filter_by(enabled=True).all()

        models = []
        for provider in enabled_providers:
            model_info = {
                "provider": provider.provider,
                "model": provider.default_model,
                "display_name": f"{provider.provider.title()} - {provider.default_model}",
                "recommended_for": [],
            }

            # Add recommendations based on provider/model
            if provider.provider == "openai" and "gpt-4o" in provider.default_model:
                model_info["recommended_for"] = ["General conversation", "Complex analysis"]
            elif provider.provider == "huggingface" and "flan-t5" in provider.default_model:
                model_info["recommended_for"] = ["Enterprise architecture", "Instruction following"]
            elif provider.provider == "anthropic":
                model_info["recommended_for"] = ["Complex reasoning", "Analysis"]
            elif provider.provider == "gemini":
                model_info["recommended_for"] = ["Multi-modal", "General tasks"]
            elif provider.provider == "deepseek":
                model_info["recommended_for"] = ["Code analysis", "Technical tasks"]

            models.append(model_info)

        return jsonify(
            {
                "success": True,
                "models": models,
                "current_provider": models[0]["provider"] if models else None,
                "current_model": models[0]["model"] if models else None,
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error getting available models: {str(e)}")
        # Return fallback models instead of error to keep UI functional
        return jsonify(
            {
                "success": True,
                "models": [
                    {
                        "provider": "huggingface",
                        "model": "google/flan-t5-base",
                        "display_name": "HuggingFace - Flan-T5",
                        "recommended_for": ["General tasks"],
                    },
                    {
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "display_name": "OpenAI - GPT-4o Mini",
                        "recommended_for": ["Complex analysis"],
                    },
                ],
                "current_provider": "huggingface",
                "current_model": "google/flan-t5-base",
                "warning": "Could not load configured models, showing defaults",
            }
        )


# ENT-043: LLM health endpoint — polled by the UI health banner
@unified_ai_chat_bp.route("/api/health/llm", methods=["GET"])
@login_required
def llm_health():
    """Return current LLM provider status (healthy | degraded | offline)."""
    try:
        from app.models.models import APISettings  # dead-code-ok: conditional import

        active = APISettings.query.filter_by(enabled=True).first()
        if active:
            return jsonify({"status": "healthy", "provider": active.provider, "model": active.default_model})
        return jsonify({"status": "degraded", "provider": None, "model": None})
    except Exception:
        return jsonify({"status": "degraded", "provider": None, "model": None})


@unified_ai_chat_bp.route("/message", methods=["POST"])
@login_required
def send_message():
    """
    Send chat message
    ---
    tags:
      - AI Chat
    summary: Send a message to the AI assistant
    description: Send a message to the AI chat system with optional domain context and persona
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - message
          properties:
            message:
              type: string
              description: User message content
            domain:
              type: string
              default: general
              description: Domain context (general, capabilities, applications, etc.)
            template_name:
              type: string
              default: General Inquiry
            element_id:
              type: integer
              description: Context element ID
            context_type:
              type: string
              description: Type of context element
            persona:
              type: string
              description: AI persona to use
            model:
              type: string
              description: Specific model to use
    responses:
      200:
        description: AI response
        schema:
          type: object
          properties:
            success:
              type: boolean
            response:
              type: string
            domain:
              type: string
            template:
              type: string
      400:
        description: Message content is required
      500:
        description: Server error
    """

    data = request.json
    user_message = data.get("message")
    domain = data.get("domain", "general")
    template_name = data.get("template_name", "General Inquiry")
    context_element_id = data.get("element_id")
    context_type = data.get("context_type")
    persona = data.get("persona")  # Extract persona from request
    requested_model = data.get("model")  # Allow model selection

    if not user_message:
        return jsonify({"error": "Message content is required"}), 400

    # ENT-041: enforce role-aware rate limit before hitting the LLM.
    user_id_for_rl = getattr(current_user, "id", None) if current_user else None
    if user_id_for_rl is not None:
        limit = _get_role_rate_limit(current_user)
        if not _check_rate_limit(user_id_for_rl, limit):
            return (
                jsonify({
                    "error": f"Rate limit exceeded ({limit} requests/hour for your role). Please try again later.",
                    "error_type": "rate_limit",
                }),
                429,
            )

    try:
        # Get multi-domain chat service
        chat_service = get_chat_service()

        # Prepare context data
        context_data = {}
        if context_element_id and context_type:
            context_data = {
                "element_id": context_element_id,
                "context_type": context_type,
                "domain": domain,
            }

        # Add document context from uploaded documents
        document_context = data.get("document_context", {})
        if document_context:
            context_data.update(document_context)

        # Process message through chat service
        response = chat_service.process_message(
            message=user_message,
            domain=domain,
            template=template_name,
            context=context_data,
            persona=persona,
            requested_model=requested_model,
        )

        return jsonify(
            {
                "success": True,
                "response": response.get("response", ""),
                "domain": response.get("domain", domain),
                "confidence": response.get("confidence", 0.0),
                "metadata": response.get("metadata", {}),
                "context_used": response.get("context_used", False),
            }
        )

    except ValueError as e:
        current_app.logger.error(f"Validation error in chat message: {str(e)}")
        return jsonify({"error": f"Invalid input: {str(e)}", "error_type": "validation"}), 400
    except ConnectionError as e:
        current_app.logger.error(f"LLM connection error: {str(e)}")
        return (
            jsonify(
                {
                    "error": "Unable to connect to AI service. Please check your API configuration in Admin > API Settings.",
                    "error_type": "connection",
                }
            ),
            503,
        )
    except TimeoutError as e:
        current_app.logger.error(f"LLM timeout error: {str(e)}")
        return (
            jsonify(
                {
                    "error": "AI service request timed out. Please try again or use a shorter message.",
                    "error_type": "timeout",
                }
            ),
            504,
        )
    except Exception as e:
        error_msg = str(e)
        current_app.logger.error(f"Error processing chat message: {error_msg}", exc_info=True)

        # Provide more specific error messages based on error content
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
            return (
                jsonify(
                    {
                        "error": "AI service authentication failed. Please verify your API key in Admin > API Settings.",
                        "error_type": "auth",
                    }
                ),
                401,
            )
        elif "rate limit" in error_msg.lower() or "quota" in error_msg.lower():
            return (
                jsonify(
                    {
                        "error": "AI service rate limit exceeded. Please wait a moment and try again.",
                        "error_type": "rate_limit",
                    }
                ),
                429,
            )
        elif "model" in error_msg.lower() and (
            "not found" in error_msg.lower() or "invalid" in error_msg.lower()
        ):
            return (
                jsonify(
                    {
                        "error": "The selected AI model is not available. Please select a different model.",
                        "error_type": "model_error",
                    }
                ),
                400,
            )
        else:
            return (
                jsonify(
                    {
                        "error": "Failed to process message. Please try again.",
                        "error_type": "unknown",
                        "details": error_msg if current_app.debug else None,
                    }
                ),
                500,
            )


@unified_ai_chat_bp.route("/domains", methods=["GET"])
@login_required
def get_available_domains():
    """Get available chat domains."""
    try:
        chat_service = get_chat_service()
        domains = chat_service.get_available_domains()
        return jsonify({"success": True, "domains": domains})
    except Exception as e:
        return jsonify({"error": "Failed to get domains", "details": str(e)}), 500


@unified_ai_chat_bp.route("/personas", methods=["GET"])
@login_required
def get_available_personas():
    """
    Get available personas
    ---
    tags:
      - AI Chat
    summary: List available AI personas
    description: Get all available chat personas for different interaction styles
    security:
      - cookieAuth: []
    responses:
      200:
        description: Available personas
        schema:
          type: object
          properties:
            success:
              type: boolean
            personas:
              type: array
              items:
                type: object
      401:
        description: Unauthorized
      500:
        description: Server error
    """
    try:
        chat_service = get_chat_service()
        personas = chat_service.get_available_personas()
        return jsonify({"success": True, "personas": personas})
    except Exception as e:
        return jsonify({"error": "Failed to get personas", "details": str(e)}), 500


@unified_ai_chat_bp.route("/templates", methods=["GET"])
@login_required
def get_prompt_templates():
    """
    Get prompt templates
    ---
    tags:
      - AI Chat
    summary: List available prompt templates
    description: Get all available AI prompt templates for different domains
    security:
      - cookieAuth: []
    responses:
      200:
        description: Available templates
        schema:
          type: object
          properties:
            success:
              type: boolean
            templates:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  name:
                    type: string
                  description:
                    type: string
                  domain:
                    type: string
                  template_text:
                    type: string
      401:
        description: Unauthorized
      500:
        description: Server error
    """
    try:
        templates = AIPromptTemplate.query.limit(200).all()
        template_list = []
        for template in templates:
            template_list.append(
                {
                    "id": template.id,
                    "name": template.name,
                    "description": template.description,
                    "domain": template.domain,
                    "template_text": template.template_text,
                }
            )
        return jsonify({"success": True, "templates": template_list})
    except Exception as e:
        return jsonify({"error": "Failed to get templates", "details": str(e)}), 500


# ============================================================================
# DATA INTERACTION ROUTES (AI-DRIVEN DATA MODIFICATIONS)
# ============================================================================


@unified_ai_chat_bp.route("/data/create-capability", methods=["POST"])
@login_required
def create_capability():
    """
    Create a new business capability through AI interaction.

    Expected JSON payload:
    {
        "name": "Capability Name",
        "description": "Capability description",
        "level": "Strategic",
        "business_domain": "Domain",
        "maturity_level": "Defined"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        service = AIDataInteractionService(user_id=current_user.id)
        result = service.create_capability(data)

        if result["success"]:
            return jsonify(
                {
                    "success": True,
                    "capability_id": result["capability_id"],
                    "message": result["message"],
                }
            )
        else:
            return jsonify({"success": False, "error": result["error"]}), 400

    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to create capability: {str(e)}"}), 500


@unified_ai_chat_bp.route("/data/update-capability/<int:capability_id>", methods=["PUT"])
@login_required
def update_capability(capability_id):
    """
    Update an existing business capability.

    Expected JSON payload:
    {
        "name": "Updated Name",
        "description": "Updated description",
        "level": "Updated level"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        service = AIDataInteractionService(user_id=current_user.id)
        result = service.update_capability(capability_id, data)

        if result["success"]:
            return jsonify(
                {
                    "success": True,
                    "capability_id": result["capability_id"],
                    "message": result["message"],
                }
            )
        else:
            return jsonify({"success": False, "error": result["error"]}), 400

    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to update capability: {str(e)}"}), 500


@unified_ai_chat_bp.route("/data/add-compliance-requirement", methods=["POST"])
@login_required
def add_compliance_requirement():
    """
    Add a compliance requirement to a capability.

    Expected JSON payload:
    {
        "capability_id": 123,
        "requirement_type": "SOX",
        "description": "Compliance requirement description",
        "priority": "High"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        service = AIDataInteractionService(user_id=current_user.id)
        result = service.add_compliance_requirement(data)

        if result["success"]:
            return jsonify(
                {
                    "success": True,
                    "requirement_id": result["requirement_id"],
                    "message": result["message"],
                }
            )
        else:
            return jsonify({"success": False, "error": result["error"]}), 400

    except Exception as e:
        return (
            jsonify({"success": False, "error": f"Failed to add compliance requirement: {str(e)}"}),
            500,
        )


@unified_ai_chat_bp.route("/data/update-application/<int:app_id>", methods=["PUT"])
@login_required
def update_application_metadata(app_id):
    """
    Update application metadata through AI interaction.

    Expected JSON payload:
    {
        "name": "Updated App Name",
        "description": "Updated description",
        "criticality": "High",
        "technology_stack": "Updated stack"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        service = AIDataInteractionService(user_id=current_user.id)
        result = service.update_application_metadata(app_id, data)

        if result["success"]:
            return jsonify(
                {
                    "success": True,
                    "application_id": result["application_id"],
                    "message": result["message"],
                }
            )
        else:
            return jsonify({"success": False, "error": result["error"]}), 400

    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to update application: {str(e)}"}), 500


@unified_ai_chat_bp.route("/data/validate-request", methods=["POST"])
@login_required
def validate_modification_request():
    """
    Validate if a data modification request is safe and allowed.

    Expected JSON payload:
    {
        "request_type": "create_capability",
        "data": {...},
        "context": "Additional context"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        service = AIDataInteractionService(user_id=current_user.id)
        result = service.validate_request(data)

        return jsonify(
            {
                "success": True,
                "is_valid": result["is_valid"],
                "risk_level": result["risk_level"],
                "warnings": result.get("warnings", []),
                "recommendations": result.get("recommendations", []),
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": f"Validation failed: {str(e)}"}), 500


# ============================================================================
# BUSINESS OUTPUT TRANSFORMATION ROUTES
# ============================================================================


@unified_ai_chat_bp.route("/transform-output", methods=["POST"])
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
        return jsonify({"error": "Transformation failed", "details": str(e)}), 500


@unified_ai_chat_bp.route("/available-roles", methods=["GET"])
@login_required
def get_available_roles():
    """Get list of available stakeholder roles."""
    try:
        service = BusinessOutputService()
        roles = service.get_available_roles()

        return jsonify({"success": True, "roles": roles})

    except Exception as e:
        return jsonify({"error": "Failed to get roles", "details": str(e)}), 500


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
        return jsonify({"error": "Failed to get role info", "details": str(e)}), 500


@unified_ai_chat_bp.route("/batch-transform", methods=["POST"])
@login_required
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
                        {"success": True, "role": role_value, "transformed_output": transformed}
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
                    {"success": False, "role": role_value, "error": "Missing ai_response or role"}
                )

        return jsonify({"success": True, "results": results})

    except Exception as e:
        return jsonify({"error": "Batch transformation failed", "details": str(e)}), 500


# ============================================================================
# ENTITY MATCHING ROUTES
# ============================================================================


@unified_ai_chat_bp.route("/entities/match", methods=["POST"])
@login_required
def match_entities():
    """Match entities based on input text using AI."""
    try:
        data = request.get_json()
        text = data.get("text", "")
        entity_types = data.get("entity_types", [])  # Optional: limit to specific entity types
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
        current_app.logger.error(f"Error in match_entities: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@unified_ai_chat_bp.route("/entities/types", methods=["GET"])
@login_required
def get_entity_types():
    """Get available entity types for matching."""
    try:
        service = ChatEntityMatchingService()
        entity_types = service.get_available_entity_types()

        return jsonify({"success": True, "entity_types": entity_types})

    except Exception as e:
        return jsonify({"error": "Failed to get entity types", "details": str(e)}), 500


@unified_ai_chat_bp.route("/entities/suggest", methods=["POST"])
@login_required
def suggest_entities():
    """
    Suggest entities based on partial input or context.

    Expected JSON payload:
    {
        "partial_text": "App name starts with...",
        "context": {"domain": "applications"},
        "limit": 5
    }
    """
    try:
        data = request.get_json()
        partial_text = data.get("partial_text", "")
        context = data.get("context", {})
        limit = data.get("limit", 10)

        if not partial_text:
            return jsonify({"error": "Partial text is required"}), 400

        service = ChatEntityMatchingService()
        suggestions = service.suggest_entities(partial_text, context, limit)

        return jsonify({"success": True, "suggestions": suggestions, "partial_text": partial_text})

    except Exception as e:
        return jsonify({"error": "Failed to get suggestions", "details": str(e)}), 500


# ============================================================================
# ARCHITECTURE GENERATION ROUTES
# ============================================================================


@unified_ai_chat_bp.route("/architecture/generate", methods=["POST"])
@login_required
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
        return jsonify({"error": "Architecture generation failed", "details": str(e)}), 500


@unified_ai_chat_bp.route("/architecture/validate", methods=["POST"])
@login_required
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
        return jsonify({"error": "Architecture validation failed", "details": str(e)}), 500


# ============================================================================
# CHAT HISTORY AND SESSION MANAGEMENT
# ============================================================================


@unified_ai_chat_bp.route("/history", methods=["GET"])
@login_required
def get_chat_history():
    """Get user's chat history."""
    try:
        chat_service = get_chat_service()
        history = chat_service.get_chat_history(current_user.id)

        return jsonify({"success": True, "history": history})

    except Exception as e:
        return jsonify({"error": "Failed to get chat history", "details": str(e)}), 500


@unified_ai_chat_bp.route("/history/clear", methods=["POST"])
@login_required
def clear_chat_history():
    """Clear user's chat history."""
    try:
        chat_service = get_chat_service()
        result = chat_service.clear_chat_history(current_user.id)

        return jsonify(
            {
                "success": result.get("success", False),
                "message": result.get("message", "History cleared"),
            }
        )

    except Exception as e:
        return jsonify({"error": "Failed to clear history", "details": str(e)}), 500


# ENT-050: Cross-session pgvector semantic search endpoint
@unified_ai_chat_bp.route("/history/similar", methods=["GET"])
@login_required
def get_similar_messages():
    """Return semantically similar chat messages for the current user across all sessions.

    Query params:
      q     (required): natural-language query text
      limit (optional): max results, default 5
    """
    query_text = request.args.get("q", "").strip()
    if not query_text:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    limit = min(int(request.args.get("limit", 5)), 20)  # fabricated-values-ok: cap at 20 results
    try:
        from app.modules.ai_chat.services.ai_chat_memory_service import get_chat_memory_service

        memory_svc = get_chat_memory_service(user_id=current_user.id)
        results = memory_svc.search_similar_messages(query_text=query_text, limit=limit)
        return jsonify({"success": True, "results": results, "count": len(results)})
    except Exception as e:
        return jsonify({"error": "Similarity search failed", "details": str(e)}), 500


@unified_ai_chat_bp.route("/session/save", methods=["POST"])
@login_required
def save_chat_session():
    """
    Save current chat session.

    Expected JSON payload:
    {
        "session_name": "Customer Analysis Session",
        "messages": [...],
        "context": {}
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        chat_service = get_chat_service()
        result = chat_service.save_session(current_user.id, data)

        return jsonify(
            {
                "success": result.get("success", False),
                "session_id": result.get("session_id"),
                "message": result.get("message", "Session saved"),
            }
        )

    except Exception as e:
        return jsonify({"error": "Failed to save session", "details": str(e)}), 500


@unified_ai_chat_bp.route("/sessions", methods=["GET"])
@login_required
def get_saved_sessions():
    """Get user's saved chat sessions."""
    try:
        chat_service = get_chat_service()
        sessions = chat_service.list_sessions(current_user.id)

        return jsonify({"success": True, "sessions": sessions})

    except Exception as e:
        return jsonify({"error": "Failed to get sessions", "details": str(e)}), 500


@unified_ai_chat_bp.route("/session/<session_id>", methods=["GET"])
@login_required
def load_chat_session(session_id):
    """Load a saved chat session."""
    try:
        chat_service = get_chat_service()
        result = chat_service.load_session(session_id)

        if result.get("success"):
            return jsonify(result)
        else:
            return jsonify({"error": result.get("error", "Session not found")}), 404

    except Exception as e:
        return jsonify({"error": "Failed to load session", "details": str(e)}), 500


# ============================================================================
# ANALYTICS AND MONITORING
# ============================================================================


@unified_ai_chat_bp.route("/analytics/usage", methods=["GET"])
@login_required
def get_usage_analytics():
    """Get AI chat usage analytics for the current user."""
    try:
        chat_service = get_chat_service()
        analytics = chat_service.get_usage_analytics(current_user.id)

        return jsonify({"success": True, "analytics": analytics})

    except Exception as e:
        return jsonify({"error": "Failed to get analytics", "details": str(e)}), 500


@unified_ai_chat_bp.route("/analytics/domains", methods=["GET"])
@login_required
def get_domain_analytics():
    """Get usage analytics by domain."""
    try:
        chat_service = get_chat_service()
        analytics = chat_service.get_domain_analytics()

        return jsonify({"success": True, "analytics": analytics})

    except Exception as e:
        return jsonify({"error": "Failed to get domain analytics", "details": str(e)}), 500


@unified_ai_chat_bp.route("/analytics/quality", methods=["GET"])
@login_required
def get_quality_metrics():
    """Get AI response quality metrics."""
    try:
        chat_service = get_chat_service()
        metrics = chat_service.get_quality_metrics()

        return jsonify({"success": True, "metrics": metrics})

    except Exception as e:
        return jsonify({"error": "Failed to get quality metrics", "details": str(e)}), 500


@unified_ai_chat_bp.route("/extensions/analytics/portfolio-health", methods=["GET"])
@login_required
def get_portfolio_health():
    """Get portfolio health score and metrics."""
    try:
        scope = request.args.get("scope", "all")

        chat_service = get_chat_service()
        result = chat_service.get_advanced_analytics("portfolio_health", {"scope": scope})

        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error getting portfolio health: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# DOMAIN CONTEXT ROUTES
# ============================================================================


@unified_ai_chat_bp.route("/context/<domain>")
@login_required
def get_domain_context(domain):
    """Get context data for specific domain."""
    try:
        chat_service = get_chat_service()
        context_data = chat_service.get_domain_context(domain)
        return jsonify(context_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# NATURAL LANGUAGE QUERY ROUTES
# ============================================================================


@unified_ai_chat_bp.route("/nl-query", methods=["POST"])
@login_required
def natural_language_query():
    """
    Process a natural language query against the database.

    Expected JSON body:
    {
        "query": "Show me all applications without business owner",
        "persona": "enterprise_architect" (optional)
    }
    """
    try:
        from app.services.natural_language_query_service import NaturalLanguageQueryService

        data = request.get_json()
        if not data or not data.get("query"):
            return jsonify({"success": False, "error": "Query is required"}), 400

        query = data.get("query")
        persona = data.get("persona")

        nl_service = NaturalLanguageQueryService()
        result = nl_service.process_query(query, persona)

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Error processing NL query: {e}", exc_info=True)
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "suggestions": [
                        "Try: 'Show all applications without business owner'",
                        "Try: 'List capabilities with maturity below 3'",
                        "Try: 'Which vendors expire in 90 days?'",
                    ],
                }
            ),
            500,
        )


@unified_ai_chat_bp.route("/nl-query/examples")
@login_required
def get_query_examples():
    """Get example queries for the NL Query interface."""
    try:
        from app.services.natural_language_query_service import NaturalLanguageQueryService

        nl_service = NaturalLanguageQueryService()
        examples = nl_service.get_supported_queries()
        return jsonify(examples)

    except Exception as e:
        current_app.logger.error(f"Error getting query examples: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# RECOMMENDATIONS ENGINE ROUTES
# ============================================================================


@unified_ai_chat_bp.route("/recommendations")
@login_required
def get_recommendations():
    """
    Get actionable recommendations and alerts.

    Query params:
    - persona: Filter by persona (optional)
    - refresh: Force refresh cache (optional)
    """
    try:
        from app.services.recommendations_engine_service import RecommendationsEngineService

        persona = request.args.get("persona")
        refresh = request.args.get("refresh", "false").lower() == "true"

        rec_service = RecommendationsEngineService()
        recommendations = rec_service.get_all_recommendations(persona=persona, refresh=refresh)

        return jsonify(recommendations)
    except Exception as e:
        current_app.logger.error(f"Error getting recommendations: {e}", exc_info=True)
        return (
            jsonify(
                {"error": str(e), "alerts": [], "recommendations": [], "summary": {"total": 0}}
            ),
            500,
        )


@unified_ai_chat_bp.route("/recommendations/quick-stats")
@login_required
def get_quick_stats():
    """Get quick statistics for dashboard display."""
    try:
        from app.services.recommendations_engine_service import RecommendationsEngineService

        rec_service = RecommendationsEngineService()
        stats = rec_service.get_quick_stats()

        return jsonify(stats)
    except Exception as e:
        current_app.logger.error(f"Error getting quick stats: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@unified_ai_chat_bp.route("/recommendations/alerts")
@login_required
def get_alerts_only():
    """Get only alerts (for notification badges, etc.)."""
    try:
        from app.services.recommendations_engine_service import RecommendationsEngineService

        persona = request.args.get("persona")
        rec_service = RecommendationsEngineService()
        data = rec_service.get_all_recommendations(persona=persona)

        # Return only alerts with summary
        return jsonify(
            {
                "alerts": data.get("alerts", []),
                "summary": data.get("summary", {}),
                "health_score": data.get("health_score", 0),
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error getting alerts: {e}", exc_info=True)
        return jsonify({"error": str(e), "alerts": []}), 500


# ============================================================================
# DOCUMENT UPLOAD AND MANAGEMENT ROUTES
# ============================================================================


@unified_ai_chat_bp.route("/upload-document", methods=["POST"])
@login_required
def upload_document():
    """
    Upload document and automatically create ArchiMate elements in Architecture CRUD.

    Extracts elements from uploaded documents and creates them in the appropriate tables.
    Supports context-aware analysis for applications and vendors.
    """
    try:
        from werkzeug.utils import secure_filename

        from app.archimate_crud.routes import LAYER_CONFIG, MODEL_REGISTRY
        from app.services.archimate.document_analysis_service import DocumentAnalysisService
        from app.services.core.async_utils import get_or_create_event_loop
        from app.services.core.retry_handler import execute_with_db_retry

        if "file" not in request.files:
            return jsonify({"success": False, "error": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"success": False, "error": "No file selected"}), 400

        # Get user ID
        user_id = current_user.id if current_user.is_authenticated else None

        # Get context-aware parameters
        analysis_context = request.form.get(
            "analysis_context", "general"
        )  # 'general', 'application', or 'vendor'
        target_application_id = request.form.get("target_application_id")
        target_vendor_id = request.form.get("target_vendor_id")

        # Get provider from form data (user selection)
        requested_provider = request.form.get("provider", "").strip().lower()

        # Convert IDs to integers if provided
        if target_application_id:
            try:
                target_application_id = int(target_application_id)
            except ValueError:
                target_application_id = None

        if target_vendor_id:
            try:
                target_vendor_id = int(target_vendor_id)
            except ValueError:
                target_vendor_id = None

        # Check if this is preview-only mode (extract but don't create)
        preview_only = request.form.get("preview_only", "false").lower() == "true"

        current_app.logger.info(
            f"Document upload - Context: {analysis_context}, App ID: {target_application_id}, Vendor ID: {target_vendor_id}, Preview: {preview_only}, Requested Provider: {requested_provider}"
        )

        # Save file
        filename = secure_filename(file.filename)
        upload_dir = os.path.join(
            current_app.config.get("UPLOAD_FOLDER", "uploads"), "ai_chat_documents"
        )
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)

        # Determine file type
        file_ext = os.path.splitext(filename)[1].lower()
        file_type = "document"
        if file_ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"]:
            file_type = "image"
        elif file_ext in [".xlsx", ".xls", ".csv"]:
            file_type = "spreadsheet"

        # Create upload record
        from app.models.ai_chat_document import AIChatDocumentUpload

        upload_record = AIChatDocumentUpload(
            file_name=filename,
            original_filename=file.filename,
            file_path=file_path,
            file_size=os.path.getsize(file_path),
            file_type=file_type,
            uploaded_by_id=user_id,
            status="analyzing" if not preview_only else "preview",
            upload_progress=0,
        )
        db.session.add(upload_record)
        db.session.commit()

        # Check if simple parsing is requested (bypass LLM)
        use_simple_parsing = request.form.get("use_simple_parsing", "false").lower() == "true"

        # Initialize provider_name for use later (even if simple parsing)
        provider_name = None
        model = None

        if use_simple_parsing:
            # Use simple parser (no LLM) - only works for CSV/Excel
            from app.services.archimate.simple_parser_service import SimpleParserService

            simple_parser = SimpleParserService()
            extracted_data = simple_parser.parse_document(
                file_path=file_path,
                analysis_context=analysis_context,
                target_application_id=target_application_id,
                target_vendor_id=target_vendor_id,
            )
            interaction = None
            interactions = []
            current_app.logger.info(f"Using simple parsing (no LLM) for {filename}")
        else:
            # Use AI-powered analysis
            analysis_service = DocumentAnalysisService()

            # Get or create event loop for async operations
            loop = get_or_create_event_loop()

            # Determine extraction context based on analysis_context parameter
            extraction_context = "architecture"
            if analysis_context == "application" and target_application_id:
                extraction_context = f"application:{target_application_id}"
            elif analysis_context == "vendor" and target_vendor_id:
                extraction_context = f"vendor:{target_vendor_id}"

            # Get provider - use requested provider if valid, otherwise fall back to configured default
            provider_name, model = LLMService._get_configured_provider()

            if requested_provider:
                # Validate requested provider exists and is enabled
                from app.models.models import APISettings

                provider_settings = APISettings.query.filter_by(
                    provider=requested_provider, enabled=True
                ).first()

                if provider_settings and provider_settings.api_key:
                    provider_name = requested_provider
                    model = provider_settings.default_model or model
                    current_app.logger.info(
                        f"✅ Using requested provider: {provider_name} with model: {model}"
                    )
                else:
                    current_app.logger.warning(
                        f"⚠️ Requested provider '{requested_provider}' not available or not enabled. "
                        f"Settings found: {provider_settings is not None}, "
                        f"Has key: {provider_settings.api_key if provider_settings else False}, "
                        f"Falling back to default: {provider_name}"
                    )
            else:
                current_app.logger.info(f"No provider requested, using default: {provider_name}")

            upload_record.provider = provider_name

            # Analyze based on file type
            if file_type == "image":
                extracted_data, interaction = loop.run_until_complete(
                    analysis_service._analyze_image(file_path, provider_name, extraction_context)
                )
                interactions = [interaction] if interaction else []
            elif file_type == "document":
                extracted_data, interactions = loop.run_until_complete(
                    analysis_service._analyze_document(file_path, provider_name, extraction_context)
                )
                interaction = interactions[0] if interactions else None
            elif file_type == "spreadsheet":
                extracted_data, interaction = analysis_service._analyze_spreadsheet(
                    file_path, provider_name, analysis_type=extraction_context
                )
                interactions = [interaction] if interaction else []
            else:
                extracted_data, interaction = loop.run_until_complete(
                    analysis_service._analyze_text_file(
                        file_path, provider_name, extraction_context
                    )
                )
                interactions = [interaction] if interaction else []

        # Log extracted data for debugging
        current_app.logger.info(f"Document analysis result keys: {list(extracted_data.keys())}")
        current_app.logger.info(f"Extracted data metadata: {extracted_data.get('metadata', {})}")

        # Extract ArchiMate elements
        archimate_elements = extracted_data.get("elements", [])
        relationships = extracted_data.get("relationships", [])

        # Normalize element types to match MODEL_REGISTRY
        from app.services.archimate.element_type_normalizer import ElementTypeNormalizer

        normalizer = ElementTypeNormalizer()
        archimate_elements = normalizer.normalize_elements(archimate_elements)

        # Log what was extracted
        current_app.logger.info(
            f"Found {len(archimate_elements)} elements (after normalization) and {len(relationships)} relationships"
        )
        if archimate_elements:
            current_app.logger.info(
                f"Sample elements: {[e.get('name', 'Unknown') + ' (' + e.get('type', 'Unknown') + ')' for e in archimate_elements[:3]]}"
            )
        else:
            # Check if there's an error in metadata
            metadata = extracted_data.get("metadata", {})
            if "error" in metadata:
                current_app.logger.error(f"Document analysis error: {metadata.get('error')}")

        # PREVIEW MODE: Return extracted elements without creating them
        if preview_only:
            current_app.logger.info(
                f"Preview mode: returning {len(archimate_elements)} extracted elements without creating"
            )

            # If no elements found, provide helpful error message
            if len(archimate_elements) == 0:
                metadata = extracted_data.get("metadata", {})
                error_message = metadata.get(
                    "error", "No ArchiMate elements could be identified in the document."
                )
                error_type = metadata.get("error_type", "no_elements")
                suggestion = metadata.get(
                    "suggestion",
                    "Try uploading a document with application names, system descriptions, or architecture diagrams.",
                )

                current_app.logger.warning(f"Preview mode: No elements extracted - {error_message}")

                # If it's an LLM error, provide specific guidance
                if error_type == "llm_error" or "failed to generate" in error_message.lower():
                    suggestion = "The LLM provider failed to process this document. Try: 1) Using Simple Parsing mode, 2) Switching to Claude/GPT-4 provider, or 3) Uploading a smaller document."
                elif error_type == "chunk_too_large":
                    suggestion = "Document chunks are too large for the selected provider. Try: 1) Using Simple Parsing mode, 2) Switching to Claude/GPT-4 provider, or 3) Breaking the document into smaller files."

                return jsonify(
                    {
                        "success": True,
                        "message": "Document analyzed but no elements found",
                        "preview_mode": True,
                        "extracted_elements": [],
                        "relationships": [],
                        "metadata": {
                            **metadata,
                            "error": error_message,
                            "error_type": error_type,
                            "suggestion": suggestion,
                        },
                        "file_name": filename,
                        "upload_id": upload_record.id if upload_record else None,
                        "preview_analysis": {
                            "total_elements": 0,
                            "elements_with_missing_fields": 0,
                            "elements_with_duplicates": 0,
                            "average_completeness_score": 0,
                            "elements_with_generated_suggestions": 0,
                        },
                    }
                )

            # ENHANCED: Analyze missing fields and generate suggestions
            from app.services.archimate.confidence_scoring_service import ConfidenceScoringService
            from app.services.archimate.entity_resolution_service import EntityResolutionService
            from app.services.archimate.knowledge_graph_service import KnowledgeGraphService
            from app.services.archimate.missing_fields_analyzer import MissingFieldsAnalyzer

            analyzer = MissingFieldsAnalyzer()
            confidence_service = ConfidenceScoringService()
            entity_resolution_service = EntityResolutionService()
            kg_service = KnowledgeGraphService()

            # Use the same provider that was requested for the main analysis (if not simple parsing)
            # Get the provider that was actually used (from requested_provider or default)
            analysis_provider = None
            if not use_simple_parsing:
                if provider_name:
                    analysis_provider = provider_name
                elif requested_provider:
                    # Fallback: use requested provider even if main analysis failed
                    from app.models.models import APISettings

                    provider_settings = APISettings.query.filter_by(
                        provider=requested_provider, enabled=True
                    ).first()
                    if provider_settings and provider_settings.api_key:
                        analysis_provider = requested_provider

            # Analyze missing fields for each element and add enhancements
            # OPTIMIZATION: For preview mode with many elements, skip expensive LLM field generation
            # to avoid timeout. Only analyze first 50 elements for field generation.
            MAX_FIELD_GENERATION_ELEMENTS = 50
            should_generate_fields = len(archimate_elements) <= MAX_FIELD_GENERATION_ELEMENTS

            if not should_generate_fields:
                current_app.logger.info(
                    f"Skipping LLM field generation for {len(archimate_elements)} elements "
                    f"(limit: {MAX_FIELD_GENERATION_ELEMENTS}) to prevent timeout"
                )

            analyzed_elements = []
            for idx, elem in enumerate(archimate_elements):
                # Analyze missing fields (lightweight operation)
                analyzed = analyzer.analyze_missing_fields(
                    [elem], elem.get("type", "ApplicationComponent")
                )
                if analyzed:
                    analyzed_elem = analyzed[0]

                    # Generate missing fields ONLY if:
                    # 1. We're within the limit (or preview mode with few elements)
                    # 2. Important fields are missing
                    # 3. We have a valid provider
                    missing_important = analyzed_elem.get("missing_fields", {}).get("important", [])
                    if missing_important and analysis_provider and should_generate_fields:
                        # Only use LLM if we have a valid provider (not simple parsing)
                        try:
                            generated = analyzer.generate_missing_fields(
                                analyzed_elem,
                                analyzed_elem.get("type", "ApplicationComponent"),
                                use_llm=True,
                                provider=analysis_provider,
                            )
                            analyzed_elem["generated_fields"] = generated
                            analyzed_elem["has_generated_suggestions"] = True
                        except (ValueError, Exception) as e:
                            # Provider failed - skip LLM for this and remaining elements
                            if (
                                "404" in str(e)
                                or "not found" in str(e).lower()
                                or "permanent" in str(e).lower()
                            ):
                                # Mark provider as failed and break loop to avoid more attempts
                                current_app.logger.warning(
                                    f"Provider {analysis_provider} failed permanently: {e}. "
                                    f"Skipping LLM field generation for remaining elements."
                                )
                                analysis_provider = None  # Disable provider for remaining elements
                                should_generate_fields = False  # Stop trying for remaining elements
                            # Use heuristics instead
                            analyzed_elem["generated_fields"] = {}
                            analyzed_elem["has_generated_suggestions"] = False
                    else:
                        # No field generation (either skipped due to limit or no provider)
                        analyzed_elem["generated_fields"] = {}
                        analyzed_elem["has_generated_suggestions"] = False

                    analyzed_elem = analyzed_elem
                else:
                    analyzed_elem = elem.copy()

                # ENHANCEMENT: Add confidence score (lightweight, always do this)
                if confidence_service:
                    try:
                        confidence = confidence_service.score_element(
                            analyzed_elem,
                            context=None,
                            extraction_method="llm",
                            validation_result=None,
                            database_match=analyzed_elem.get("resolution", {}).get(
                                "database_match"
                            ),
                        )
                        analyzed_elem["confidence"] = confidence.to_dict()
                    except Exception as e:
                        current_app.logger.warning(f"Error calculating confidence: {e}")

                # ENHANCEMENT: Add entity resolution if not already present
                # OPTIMIZATION: Only resolve first 100 elements to prevent timeout
                if entity_resolution_service and not analyzed_elem.get("resolution") and idx < 100:
                    try:
                        resolution = entity_resolution_service.resolve_entity(
                            analyzed_elem.get("name", ""), analyzed_elem.get("type"), context=None
                        )
                        if resolution and resolution.get("confidence", 0) > 0.5:
                            analyzed_elem["resolution"] = resolution
                            # Update name if resolution found
                            if resolution.get("resolved") and resolution.get(
                                "resolved"
                            ) != analyzed_elem.get("name"):
                                analyzed_elem["resolved_name"] = resolution["resolved"]
                    except Exception as e:
                        current_app.logger.warning(f"Error resolving entity: {e}")

                # ENHANCEMENT: Add knowledge graph context
                # OPTIMIZATION: Skip KG for large datasets (expensive operation)
                if kg_service and len(archimate_elements) <= 100:
                    try:
                        kg_context = kg_service.get_semantic_context(analyzed_elem, max_context=3)
                        if kg_context:
                            analyzed_elem["kg_related_entities"] = kg_context
                    except Exception as e:
                        current_app.logger.warning(f"Error getting KG context: {e}")

                analyzed_elements.append(analyzed_elem)

            # Calculate summary statistics
            total_elements = len(analyzed_elements)
            elements_with_missing = sum(
                1 for e in analyzed_elements if e.get("missing_fields", {}).get("all_missing")
            )
            elements_with_duplicates = sum(
                1 for e in analyzed_elements if e.get("properties", {}).get("exists_in_db")
            )
            avg_completeness = (
                sum(e.get("completeness_score", 0) for e in analyzed_elements) / total_elements
                if total_elements > 0
                else 0
            )

            # Save upload record in preview state
            try:
                upload_record.status = "preview"
                upload_record.upload_progress = 100
                db.session.commit()
            except Exception as e:
                current_app.logger.warning(f"Could not update upload record for preview: {e}")

            return jsonify(
                {
                    "success": True,
                    "message": f"Preview mode: Found {len(analyzed_elements)} elements",
                    "preview_mode": True,
                    "extracted_elements": analyzed_elements,
                    "relationships": relationships,
                    "metadata": extracted_data.get("metadata", {}),
                    "file_name": filename,
                    "upload_id": upload_record.id if upload_record else None,
                    "preview_analysis": {
                        "total_elements": total_elements,
                        "elements_with_missing_fields": elements_with_missing,
                        "elements_with_duplicates": elements_with_duplicates,
                        "average_completeness_score": round(avg_completeness, 1),
                        "elements_with_generated_suggestions": sum(
                            1 for e in analyzed_elements if e.get("has_generated_suggestions")
                        ),
                    },
                }
            )

        # CREATE MODE: Create elements in database
        created_elements = []
        created_count = 0
        skipped_count = 0
        errors = []

        for elem in archimate_elements:
            try:
                element_type = elem.get("type")
                if not element_type:
                    errors.append(f"Element '{elem.get('name', 'Unknown')}' missing type field")
                    skipped_count += 1
                    continue

                model_class = MODEL_REGISTRY.get(element_type)
                if not model_class:
                    errors.append(f"Element type '{element_type}' not supported in MODEL_REGISTRY")
                    skipped_count += 1
                    current_app.logger.warning(
                        f"Unsupported element type: '{element_type}' for element '{elem.get('name', 'Unknown')}'"
                    )
                    continue

                name = elem.get("name", "").strip()
                if not name:
                    errors.append(f"Element with type '{element_type}' missing name field")
                    skipped_count += 1
                    continue

                # Check for existing element (case-insensitive)
                existing = model_class.query.filter(
                    func.lower(model_class.name) == func.lower(name)
                ).first()
                if existing:
                    current_app.logger.info(
                        f"Skipping duplicate element: {name} (type: {element_type})"
                    )
                    created_elements.append(
                        {
                            "type": element_type,
                            "name": name,
                            "id": existing.id,
                            "status": "existing",
                        }
                    )
                    continue

                # Build element data with all available fields
                element_data = {
                    "name": name,
                    "description": elem.get("description", "").strip() or None,
                }

                # Add any additional properties that the model might support
                properties = elem.get("properties", {})
                if isinstance(properties, dict):
                    for key, value in properties.items():
                        if hasattr(model_class, key) and value is not None:
                            element_data[key] = value

                # Only add created_by_id if the model supports it
                if hasattr(model_class, "created_by_id"):
                    element_data["created_by_id"] = current_user.id

                # Create the element
                new_element = model_class(**element_data)
                db.session.add(new_element)
                db.session.flush()

                # Auto-create ArchiMateElement link if the model has archimate_element_id
                if hasattr(new_element, "archimate_element_id"):
                    from app.models.archimate_core import ArchiMateElement

                    # Infer layer if not provided
                    layer = elem.get("layer")
                    if not layer:
                        layer = normalizer.infer_layer(element_type)

                    archimate_element = ArchiMateElement(
                        name=name,
                        type=element_type,
                        layer=layer if layer else None,
                        description=elem.get("description", "").strip() or None,
                    )
                    db.session.add(archimate_element)
                    db.session.flush()
                    new_element.archimate_element_id = archimate_element.id

                created_elements.append(
                    {"type": element_type, "name": name, "id": new_element.id, "status": "created"}
                )
                created_count += 1
                current_app.logger.info(
                    f"Created element: {name} (type: {element_type}, id: {new_element.id})"
                )

            except Exception as e:
                error_msg = f"Error creating {elem.get('type', 'unknown')} '{elem.get('name', 'Unknown')}': {str(e)}"
                errors.append(error_msg)
                current_app.logger.error(error_msg, exc_info=True)
                skipped_count += 1

        if created_count > 0:
            db.session.commit()

        # Update document record with consolidated retry logic
        def safe_json_dumps(data):
            """Safely serialize data to JSON."""
            try:
                return json.dumps(data, ensure_ascii=False)
            except (TypeError, ValueError) as e:
                current_app.logger.warning(f"JSON serialization error: {e}")
                return json.dumps({"error": f"Serialization error: {str(e)}"})

        def update_document_results():
            db.session.refresh(upload_record)
            upload_record.status = "completed" if not errors else "partial"
            upload_record.upload_progress = 100
            upload_record.created_elements_count = created_count
            upload_record.created_elements_details = safe_json_dumps(created_elements)
            upload_record.errors = safe_json_dumps(errors) if errors else None
            upload_record.confidence = extracted_data.get("metadata", {}).get(
                "confidence", "medium"
            )
            upload_record.analysis_results = safe_json_dumps(extracted_data)
            upload_record.analyzed_at = datetime.utcnow()
            db.session.commit()

        success, _, error = execute_with_db_retry(
            update_document_results, operation_name="update document upload results"
        )

        if not success:
            current_app.logger.error(f"Failed to update document record: {error}")
            raise Exception(f"Failed to save upload results: {error}")

        # Build comprehensive response
        response_message = f"Document analyzed. Created {created_count} new elements."
        if skipped_count > 0:
            response_message += f" Skipped {skipped_count} elements (duplicates or errors)."
        if errors:
            response_message += f" {len(errors)} errors occurred."

        return jsonify(
            {
                "success": True,
                "message": response_message,
                "analysis_results": {
                    "created_elements": created_count,
                    "skipped_elements": skipped_count,
                    "total_extracted": len(archimate_elements),
                    "created_details": created_elements,
                    "errors": errors,
                },
                "upload_id": upload_record.id,
            }
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error uploading document: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@unified_ai_chat_bp.route("/documents", methods=["GET"])
@login_required
def get_document_history():
    """Get list of uploaded documents for the current user."""
    try:
        from app.models.ai_chat_document import AIChatDocumentUpload

        # Get query parameters with pagination bounds checking
        MAX_LIMIT = 1000  # Maximum records per request
        DEFAULT_LIMIT = 50
        try:
            limit = int(request.args.get("limit", DEFAULT_LIMIT))
            limit = min(max(limit, 1), MAX_LIMIT)  # Clamp between 1 and MAX_LIMIT
        except (ValueError, TypeError):
            limit = DEFAULT_LIMIT

        try:
            offset = int(request.args.get("offset", 0))
            offset = max(offset, 0)  # Ensure non-negative
        except (ValueError, TypeError):
            offset = 0

        status_filter = request.args.get("status")  # Optional status filter

        # Build query
        query = AIChatDocumentUpload.query.filter_by(uploaded_by_id=current_user.id)

        if status_filter:
            query = query.filter_by(status=status_filter)

        # Order by most recent first
        query = query.order_by(AIChatDocumentUpload.created_at.desc())

        # Get total count
        total = query.count()

        # Get paginated results
        documents = query.limit(limit).offset(offset).all()

        return jsonify(
            {
                "success": True,
                "documents": [doc.to_dict() for doc in documents],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error fetching document history: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@unified_ai_chat_bp.route("/documents/<int:doc_id>", methods=["GET"])
@login_required
def get_document_details(doc_id):
    """Get detailed information about a specific uploaded document."""
    try:
        from app.models.ai_chat_document import AIChatDocumentUpload

        document = AIChatDocumentUpload.query.filter_by(
            id=doc_id, uploaded_by_id=current_user.id
        ).first()

        if not document:
            return jsonify({"success": False, "error": "Document not found"}), 404

        # Parse analysis results
        analysis_results = None
        if document.analysis_results:
            try:
                analysis_results = (
                    json.loads(document.analysis_results)
                    if isinstance(document.analysis_results, str)
                    else document.analysis_results
                )
            except (json.JSONDecodeError, TypeError):
                analysis_results = {"error": "Failed to parse analysis results"}

        return jsonify(
            {
                "success": True,
                "document": {
                    "id": document.id,
                    "filename": document.original_filename,
                    "file_name": document.file_name,
                    "file_size": document.file_size,
                    "file_type": document.file_type,
                    "status": document.status,
                    "uploaded_at": document.created_at.isoformat() if document.created_at else None,
                    "analyzed_at": document.analyzed_at.isoformat()
                    if document.analyzed_at
                    else None,
                    "created_elements_count": document.created_elements_count,
                    "confidence": document.confidence,
                    "summary": document.chat_context_summary,
                    "analysis_results": analysis_results,
                },
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error getting document details: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@unified_ai_chat_bp.route("/documents/<int:doc_id>", methods=["DELETE"])
@login_required
def delete_document(doc_id):
    """Delete an uploaded document record."""
    try:
        from app.models.ai_chat_document import AIChatDocumentUpload

        current_app.logger.info(
            f"Delete request for document ID: {doc_id}, user ID: {current_user.id}"
        )

        # Try to find the document
        document = AIChatDocumentUpload.query.filter_by(id=doc_id).first()

        if not document:
            current_app.logger.warning(f"Document {doc_id} not found")
            return jsonify({"success": False, "error": "Document not found"}), 404

        # Check ownership
        if document.uploaded_by_id != current_user.id:
            current_app.logger.warning(
                f"User {current_user.id} attempted to delete document {doc_id} owned by {document.uploaded_by_id}"
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Unauthorized - you can only delete your own documents",
                    }
                ),
                403,
            )

        # Delete file if it exists
        if document.file_path and os.path.exists(document.file_path):
            try:
                os.remove(document.file_path)
            except Exception as e:
                current_app.logger.warning(f"Could not delete file {document.file_path}: {e}")

        # Delete database record
        db.session.delete(document)
        db.session.commit()

        return jsonify({"success": True, "message": "Document deleted successfully"})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting document: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@unified_ai_chat_bp.route("/documents/<int:doc_id>/re-analyze", methods=["POST"])
@login_required
def re_analyze_document(doc_id):
    """Re-analyze a previously uploaded document."""
    try:
        from app.archimate_crud.routes import MODEL_REGISTRY
        from app.models.ai_chat_document import AIChatDocumentUpload
        from app.services.archimate.document_analysis_service import DocumentAnalysisService
        from app.services.core.async_utils import get_or_create_event_loop
        from app.services.core.retry_handler import execute_with_db_retry

        document = AIChatDocumentUpload.query.filter_by(
            id=doc_id, uploaded_by_id=current_user.id
        ).first()

        if not document:
            return jsonify({"success": False, "error": "Document not found or unauthorized"}), 404

        # Check if file still exists
        if not document.file_path or not os.path.exists(document.file_path):
            return jsonify({"success": False, "error": "File no longer exists"}), 404

        # Update status
        document.status = "analyzing"
        document.upload_progress = 0
        db.session.commit()

        # Analyze document
        analysis_service = DocumentAnalysisService()

        # Get or create event loop for async operations
        loop = get_or_create_event_loop()

        if document.file_type == "image":
            extracted_data, interaction = loop.run_until_complete(
                analysis_service._analyze_image(
                    document.file_path, document.provider, "architecture"
                )
            )
        elif document.file_type == "document":
            extracted_data, interactions = loop.run_until_complete(
                analysis_service._analyze_document(
                    document.file_path, document.provider, "architecture"
                )
            )
            interaction = interactions[0] if interactions else None
        else:
            extracted_data, interaction = loop.run_until_complete(
                analysis_service._analyze_text_file(
                    document.file_path, document.provider, "architecture"
                )
            )

        # Extract and create elements (same logic as upload)
        archimate_elements = extracted_data.get("elements", [])
        created_elements = []
        created_count = 0
        errors = []

        for elem in archimate_elements:
            try:
                element_type = elem.get("type")
                model_class = MODEL_REGISTRY.get(element_type)
                if not model_class:
                    errors.append(f"Element type '{element_type}' not supported")
                    continue

                name = elem.get("name", "")
                existing = model_class.query.filter_by(name=name).first()
                if existing:
                    continue

                element_data = {"name": name, "description": elem.get("description", "")}

                # Only add created_by_id if the model supports it
                if hasattr(model_class, "created_by_id"):
                    element_data["created_by_id"] = current_user.id

                new_element = model_class(**element_data)
                db.session.add(new_element)
                db.session.flush()

                # Auto-create ArchiMateElement link if the model has archimate_element_id
                if hasattr(new_element, "archimate_element_id"):
                    from app.models.archimate_core import ArchiMateElement

                    layer = elem.get("layer", "")
                    archimate_element = ArchiMateElement(
                        name=name,
                        type=element_type,
                        layer=layer if layer else None,
                        description=elem.get("description", ""),
                    )
                    db.session.add(archimate_element)
                    db.session.flush()
                    new_element.archimate_element_id = archimate_element.id

                created_elements.append(
                    {"type": element_type, "name": name, "id": new_element.id, "status": "created"}
                )
                created_count += 1

            except Exception as e:
                errors.append(f"Error creating {elem.get('type', 'unknown')}: {str(e)}")

        if created_count > 0:
            db.session.commit()

        # Update document record with consolidated retry logic
        def safe_json_dumps(data):
            """Safely serialize data to JSON."""
            try:
                return json.dumps(data, ensure_ascii=False)
            except (TypeError, ValueError) as e:
                current_app.logger.warning(f"JSON serialization error: {e}")
                return json.dumps({"error": f"Serialization error: {str(e)}"})

        def update_document_results():
            db.session.refresh(document)
            document.status = "completed" if not errors else "partial"
            document.upload_progress = 100
            document.created_elements_count = created_count
            document.created_elements_details = safe_json_dumps(created_elements)
            document.errors = safe_json_dumps(errors) if errors else None
            document.confidence = extracted_data.get("metadata", {}).get("confidence", "medium")
            document.analysis_results = safe_json_dumps(extracted_data)
            document.analyzed_at = datetime.utcnow()
            db.session.commit()

        success, _, error = execute_with_db_retry(
            update_document_results, operation_name="update re-analysis results"
        )

        if not success:
            current_app.logger.error(f"Failed to update document record: {error}")
            raise Exception(f"Failed to save re-analysis results: {error}")

        return jsonify(
            {
                "success": True,
                "message": f"Document re-analyzed. Created {created_count} new elements.",
                "analysis_results": {
                    "created_elements": created_count,
                    "created_details": created_elements,
                    "errors": errors,
                },
            }
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error re-analyzing document: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@unified_ai_chat_bp.route("/create-elements", methods=["POST"])
@login_required
def create_elements():
    """
    Create ArchiMate elements from user-selected preview list.

    This endpoint is called after preview mode to create only the elements
    the user has selected and optionally edited.

    Expected JSON body:
    {
        "elements": [{"name": "...", "type": "...", "description": "...", "layer": "..."}],
        "analysis_context": "general|application|vendor",
        "target_application_id": 123,  # optional
        "target_vendor_id": 456  # optional
    }
    """
    try:
        from app.archimate_crud.routes import MODEL_REGISTRY
        from app.models.archimate_core import ArchiMateElement

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        elements = data.get("elements", [])
        if not elements:
            return jsonify({"success": False, "error": "No elements provided"}), 400

        analysis_context = data.get("analysis_context", "general")
        target_application_id = data.get("target_application_id")
        target_vendor_id = data.get("target_vendor_id")

        # Convert IDs to integers if provided
        if target_application_id:
            try:
                target_application_id = int(target_application_id)
            except (ValueError, TypeError):
                target_application_id = None

        if target_vendor_id:
            try:
                target_vendor_id = int(target_vendor_id)
            except (ValueError, TypeError):
                target_vendor_id = None

        user_id = current_user.id if current_user.is_authenticated else None

        current_app.logger.info(
            f"Creating {len(elements)} elements - Context: {analysis_context}, App: {target_application_id}, Vendor: {target_vendor_id}"
        )

        created_elements = []
        created_count = 0
        errors = []

        # Import field mapper
        from app.ai_chat.element_field_mapper import (
            check_element_exists,
            map_element_data_to_model_fields,
        )

        for elem in elements:
            element_type = elem.get("type")
            name = elem.get("name", "").strip()
            layer = elem.get("layer", "").lower()
            description = elem.get("description", "")

            if not name:
                errors.append(f"Element with type '{element_type}' has no name - skipped")
                continue

            # Find the model class
            model_class = MODEL_REGISTRY.get(element_type)
            if not model_class:
                errors.append(f"Element type '{element_type}' not supported - skipped '{name}'")
                continue

            # Check if element already exists (using correct field name)
            existing = check_element_exists(model_class, element_type, name)
            if existing:
                created_elements.append(
                    {
                        "type": element_type,
                        "name": name,
                        "id": existing.id,
                        "status": "skipped",
                        "reason": "Already exists",
                    }
                )
                continue

            # Use savepoint for each element
            try:
                savepoint = db.session.begin_nested()

                # Map element data to model-specific fields
                element_data = map_element_data_to_model_fields(element_type, elem, user_id)

                # Only add created_by_id if the model supports it
                if hasattr(model_class, "created_by_id"):
                    element_data["created_by_id"] = user_id

                # Filter out any fields that don't exist on the model to prevent TypeError
                # This prevents errors like 'deployment_type' is an invalid keyword argument
                valid_columns = {col.key for col in inspect(model_class).columns}
                element_data = {k: v for k, v in element_data.items() if k in valid_columns}

                # Create the element
                new_element = model_class(**element_data)
                db.session.add(new_element)
                db.session.flush()

                # Auto-create ArchiMateElement link
                archimate_element = ArchiMateElement(
                    name=name,
                    type=element_type,
                    layer=layer if layer else None,
                    description=description,
                )
                db.session.add(archimate_element)
                db.session.flush()

                # Link them
                if hasattr(new_element, "archimate_element_id"):
                    new_element.archimate_element_id = archimate_element.id

                # Link to target application or vendor if specified
                linked_to = None
                if target_application_id and analysis_context == "application":
                    if hasattr(new_element, "application_id"):
                        new_element.application_id = target_application_id
                        linked_to = {"type": "application", "id": target_application_id}
                    # Also add to relationship table if available
                    try:
                        from app.models.relationship_tables import application_component_elements

                        if element_type in [
                            "ApplicationService",
                            "ApplicationInterface",
                            "DataObject",
                            "ApplicationFunction",
                        ]:
                            db.session.execute(  # tenant-filtered: scoped via parent FK (application_component_id)
                                application_component_elements.insert().values(
                                    application_component_id=target_application_id,
                                    archimate_element_id=archimate_element.id,
                                )
                            )
                            linked_to = {"type": "application", "id": target_application_id}
                    except Exception as link_error:
                        current_app.logger.warning(
                            f"Could not link element to application: {link_error}"
                        )

                elif target_vendor_id and analysis_context == "vendor":
                    if hasattr(new_element, "vendor_id"):
                        new_element.vendor_id = target_vendor_id
                        linked_to = {"type": "vendor", "id": target_vendor_id}
                    elif hasattr(new_element, "organization_id"):
                        new_element.organization_id = target_vendor_id
                        linked_to = {"type": "vendor", "id": target_vendor_id}
                    # For vendor products
                    try:
                        if element_type in ["ApplicationComponent", "TechnologyService", "Product"]:
                            from app.models.vendor.vendor_organization import VendorProduct

                            vendor_product = VendorProduct(
                                name=name,
                                description=description,
                                vendor_organization_id=target_vendor_id,
                                product_type=element_type,
                            )
                            db.session.add(vendor_product)
                            linked_to = {
                                "type": "vendor_product",
                                "id": target_vendor_id,
                                "product_name": name,
                            }
                    except Exception as vendor_link_error:
                        current_app.logger.warning(
                            f"Could not create vendor product: {vendor_link_error}"
                        )

                # Commit the savepoint
                savepoint.commit()

                created_elements.append(
                    {
                        "type": element_type,
                        "name": name,
                        "id": new_element.id,
                        "status": "created",
                        "layer": layer,
                        "linked_to": linked_to,
                    }
                )
                created_count += 1

            except Exception as e:
                try:
                    savepoint.rollback()
                except Exception:  # fabricated-values-ok: bare except intentional — rollback must not mask outer error
                    pass
                errors.append(f"Error creating {element_type} '{name}': {str(e)}")
                current_app.logger.error(f"Error creating element {name}: {e}", exc_info=True)

        # Commit all successfully created elements
        if created_count > 0:
            try:
                db.session.commit()
            except Exception as commit_error:
                db.session.rollback()
                current_app.logger.error(f"Error committing elements: {commit_error}")
                errors.append(f"Failed to commit created elements: {str(commit_error)}")

        # Build response with links to view created elements
        view_links = {}
        if target_application_id and analysis_context == "application":
            view_links["application"] = f"/dashboard/application/{target_application_id}"
            view_links[
                "application_architecture"
            ] = f"/dashboard/application/{target_application_id}#architecture"
        if target_vendor_id and analysis_context == "vendor":
            view_links["vendor"] = f"/vendors/view/{target_vendor_id}"

        return jsonify(
            {
                "success": True,
                "message": f"Created {created_count} ArchiMate elements",
                "created_count": created_count,
                "created_elements": created_elements,
                "errors": errors,
                "view_links": view_links,
            }
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating elements: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# ERROR HANDLERS
# ============================================================================


@unified_ai_chat_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({"error": "Resource not found"}), 404


@unified_ai_chat_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    current_app.logger.error(f"Internal server error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500


@unified_ai_chat_bp.errorhandler(401)
def unauthorized(error):
    """Handle 401 errors."""
    return jsonify({"error": "Unauthorized access"}), 401


@unified_ai_chat_bp.errorhandler(403)
def forbidden(error):
    """Handle 403 errors."""
    return jsonify({"error": "Access forbidden"}), 403


# ============================================================================
# LEGACY ROUTE COMPATIBILITY
# ============================================================================


# Legacy route redirects for backward compatibility
@unified_ai_chat_bp.route("/chat", strict_slashes=False)
@login_required
def legacy_chat_index():
    """Legacy redirect to main chat interface"""
    return redirect(url_for("unified_ai_chat.index"))


@unified_ai_chat_bp.route("/chat/message", methods=["POST"])
@login_required
def legacy_send_message():
    """Legacy redirect to message endpoint"""
    return send_message()


@unified_ai_chat_bp.route("/chat/data/<path:path>", strict_slashes=False)
@login_required
def legacy_data_routes(path):
    """Legacy data interaction route handler"""
    # Map legacy routes to new unified routes
    route_mapping = {
        "/create-capability": "unified_ai_chat.create_capability",
        "/update-capability/<int:capability_id>": "unified_ai_chat.update_capability",
        "/add-compliance-requirement": "unified_ai_chat.add_compliance_requirement",
        "/update-application/<int:app_id>": "unified_ai_chat.update_application_metadata",
        "/validate-request": "unified_ai_chat.validate_modification_request",
    }

    if path in route_mapping:
        # Handle routes with parameters
        if "<int:capability_id>" in route_mapping[path]:
            # Extract ID from path
            parts = path.split("/")
            if len(parts) >= 3 and parts[2].isdigit():
                capability_id = int(parts[2])
                if parts[1] == "update-capability":
                    return update_capability(capability_id)
        elif "<int:app_id>" in route_mapping[path]:
            # Extract ID from path
            parts = path.split("/")
            if len(parts) >= 3 and parts[2].isdigit():
                app_id = int(parts[2])
                if parts[1] == "update-application":
                    return update_application_metadata(app_id)
        else:
            return redirect(url_for(route_mapping[path]))
    else:
        return jsonify({"error": "Legacy route not found"}), 404


@unified_ai_chat_bp.route("/chat/transform/<path:path>", strict_slashes=False)
@login_required
def legacy_transform_routes(path):
    """Legacy business output route handler"""
    if path == "transform-output":
        return transform_output()
    elif path == "available-roles":
        return get_available_roles()
    elif path.startswith("role-info/"):
        role_value = path.replace("role-info/", "")
        return get_role_info(role_value)
    else:
        return jsonify({"error": "Legacy route not found"}), 404


# ============================================================================
# FEEDBACK & LEARNING ENDPOINTS
# ============================================================================


@unified_ai_chat_bp.route("/documents/<int:doc_id>/feedback", methods=["POST"])
@login_required
def record_feedback(doc_id):
    """Record user feedback/correction for learning."""
    try:
        from app.models.ai_chat_document import AIChatDocumentUpload
        from app.services.archimate.feedback_learning_service import FeedbackLearningService

        document = AIChatDocumentUpload.query.filter_by(
            id=doc_id, uploaded_by_id=current_user.id
        ).first()

        if not document:
            return jsonify({"success": False, "error": "Document not found"}), 404

        data = request.json
        original_element = data.get("original_element")
        corrected_element = data.get("corrected_element")

        if not original_element or not corrected_element:
            return (
                jsonify({"success": False, "error": "Missing original or corrected element"}),
                400,
            )

        # Get document hash for pattern matching
        import hashlib

        doc_hash = (
            hashlib.sha256((document.analysis_results or "").encode()).hexdigest()
            if document.analysis_results
            else None
        )

        # Get confidence before if available
        confidence_before = original_element.get("confidence", {}).get("score")

        learning_service = FeedbackLearningService()
        feedback_id = learning_service.record_correction(
            original_element=original_element,
            corrected_element=corrected_element,
            document_id=doc_id,
            document_hash=doc_hash,
            user_id=current_user.id,
            confidence_before=confidence_before,
        )

        return jsonify(
            {
                "success": True,
                "feedback_id": feedback_id,
                "message": "Feedback recorded successfully",
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error recording feedback: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@unified_ai_chat_bp.route("/documents/<int:doc_id>/compare", methods=["GET"])
@login_required
def compare_document_versions(doc_id):
    """Compare document analysis versions."""
    try:
        from app.models.ai_chat_document import AIChatDocumentUpload
        from app.services.archimate.document_comparison_service import DocumentComparisonService

        document = AIChatDocumentUpload.query.filter_by(
            id=doc_id, uploaded_by_id=current_user.id
        ).first()

        if not document:
            return jsonify({"success": False, "error": "Document not found"}), 404

        version1_id = request.args.get("version1_id", type=int)
        version2_id = request.args.get("version2_id", type=int)

        comparison_service = DocumentComparisonService()

        # Parse analysis results
        analysis1 = json.loads(document.analysis_results) if document.analysis_results else {}
        analysis2 = {}

        if version2_id:
            # Compare with another document version
            doc2 = AIChatDocumentUpload.query.get(version2_id)
            if doc2:
                analysis2 = json.loads(doc2.analysis_results) if doc2.analysis_results else {}
        else:
            # Compare with current state (if re-analyzed)
            analysis2 = analysis1.copy()

        comparison = comparison_service.compare_analyses(analysis1, analysis2)
        diff_report = comparison_service.generate_diff_report(comparison)

        return jsonify(
            {
                "success": True,
                "comparison": {
                    "summary": comparison.summary,
                    "added_elements": [
                        {"name": e.get("name"), "type": e.get("type")}
                        for e in comparison.added_elements
                    ],
                    "removed_elements": [
                        {"name": e.get("name"), "type": e.get("type")}
                        for e in comparison.removed_elements
                    ],
                    "modified_elements": [
                        {
                            "name": change.element_name,
                            "changes": {
                                field: {"old": old_val, "new": new_val}
                                for field, (old_val, new_val) in change.changes.items()
                            },
                        }
                        for change in comparison.modified_elements
                    ],
                },
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error comparing documents: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@unified_ai_chat_bp.route("/entities/resolve", methods=["POST"])
@login_required
def resolve_entity():
    """Resolve entity name (acronym expansion, normalization, etc.)."""
    try:
        from app.services.archimate.entity_resolution_service import EntityResolutionService

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
        return jsonify({"success": False, "error": str(e)}), 500


@unified_ai_chat_bp.route("/knowledge-graph/related", methods=["POST"])
@login_required
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
        return jsonify({"success": False, "error": str(e)}), 500


@unified_ai_chat_bp.route("/chat/entities/<path:path>", strict_slashes=False)
@login_required
def legacy_entity_routes(path):
    """Legacy entity matching route handler"""
    if path == "match":
        return match_entities()
    elif path == "types":
        return get_entity_types()
    elif path == "suggest":
        return suggest_entities()
    else:
        return jsonify({"error": "Legacy route not found"}), 404
