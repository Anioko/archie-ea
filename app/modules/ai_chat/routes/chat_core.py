"""
Core chat messaging, model selection, sessions, and configuration routes.

Routes: message, models, domains, personas, templates, context,
        history, history/clear, session/save, sessions, session/<id>.
"""

import logging

from flask import Response, current_app, g, jsonify, request, stream_with_context
from flask_login import current_user, login_required

from app.decorators import audit_log
from app.models.ai_service import AIPromptTemplate
from app.services.feature_flag_service import FeatureFlagService
from app.services.rate_limiter import rate_limit
from app.utils.validators import (
    sanitize_html,
    validate_chat_message,
    validate_enum,
    validate_integer,
    validate_string,
    validation_error_response,
)
from app.schemas.api_schemas import ChatMessageSchema, _load_and_validate
from . import unified_ai_chat_bp
from .chat_views import get_chat_service

logger = logging.getLogger(__name__)


def _get_configured_chat_models():
    """Return models that are actually selectable in AI chat."""
    from app.models.models import APISettings

    providers = APISettings.query.filter_by(enabled=True).all()
    models = []

    for provider in providers:
        provider_name = (provider.provider or "").strip().lower()
        if not provider_name:
            continue

        if provider_name != "huggingface" and not provider.has_key():
            continue

        raw_models = [
            m.strip() for m in (provider.default_model or "").split(",") if m and m.strip()
        ]
        if not raw_models:
            continue

        for order, model_id in enumerate(raw_models):
            model_info = {
                "provider": provider_name,
                "model": model_id,
                "display_name": f"{provider_name.title()} - {model_id}",
                "recommended_for": [],
                "fallback_order": order,
                "is_fallback": order > 0,
                "test_status": provider.test_status,
                "last_tested_at": provider.last_tested_at.isoformat()
                if provider.last_tested_at
                else None,
            }

            if provider_name == "openai" and "gpt-4o" in model_id:
                model_info["recommended_for"] = ["General conversation", "Complex analysis"]
            elif provider_name == "huggingface" and "flan-t5" in model_id:
                model_info["recommended_for"] = [
                    "Enterprise architecture",
                    "Instruction following",
                ]
            elif provider_name == "anthropic":
                model_info["recommended_for"] = ["Complex reasoning", "Analysis"]
            elif provider_name == "gemini":
                model_info["recommended_for"] = ["Multi-modal", "General tasks"]
            elif provider_name == "deepseek":
                model_info["recommended_for"] = ["Code analysis", "Technical tasks"]

            models.append(model_info)

    return models


@unified_ai_chat_bp.route("/persona-context/<persona>", methods=["GET"])
@login_required
def get_persona_context(persona):
    """AI-1: inspect what an AI Architect persona sees (charter + live data).

    Lets architects audit the persona's evidence base, and lets E2E verify
    the live-context pipeline without an LLM call.
    """
    from app.modules.ai_chat.services.architect_persona_charters import (
        ARCHITECT_PERSONAS,
        CHARTERS,
        get_live_context,
    )

    if persona not in ARCHITECT_PERSONAS:
        return jsonify({
            "success": False,
            "error": f"Not an AI Architect persona. Available: {list(ARCHITECT_PERSONAS)}",
        }), 404
    return jsonify({
        "success": True,
        "persona": persona,
        "charter_chars": len(CHARTERS.get(persona, "")),
        "live_context": get_live_context(persona),
    })


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
        models = _get_configured_chat_models()

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
        return (
            jsonify(
                {
                    "success": False,
                    "models": [],
                    "current_provider": None,
                    "current_model": None,
                    "error": "model_configuration_unavailable",
                    "message": "Could not load configured AI models.",
                }
            ),
            500,
        )


@unified_ai_chat_bp.route("/message", methods=["POST"])
@login_required
@rate_limit(30, "1h")  # LLM-003: 30 requests per hour for chat operations
@audit_log("send_chat_message")
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
    if data and "template" in data and "template_name" not in data:
        data = dict(data)
        data["template_name"] = data.pop("template")

    # Validate JSON payload exists
    if data is None:
        return validation_error_response("Request body is required")

    # T-031: marshmallow schema validation
    _schema = ChatMessageSchema()
    _validated, _err = _load_and_validate(_schema, data)
    if _err is not None:
        return _err
    data = _validated

    # Check if AI chat feature is enabled
    feature_guard = FeatureFlagService.require_ai_for_route(
        FeatureFlagService.FEATURE_CHAT, endpoint_name="send_message"
    )
    if feature_guard:
        return feature_guard

    # Validate and sanitize message content
    user_message = data.get("message")
    is_valid, validated_message, error = validate_chat_message(user_message)
    if not is_valid:
        return validation_error_response(error)
    user_message = validated_message

    # ENT-082: Check for slash commands before LLM processing
    from app.modules.ai_chat.services.command_parser_service import CommandParserService

    cmd_service = CommandParserService()
    if cmd_service.is_command(user_message):
        result = cmd_service.parse(user_message)
        if result["valid"]:
            domain_for_cmd = data.get("domain", "general")
            cmd_result = cmd_service.execute(
                result["command"], result["args"], current_user.id, domain_for_cmd
            )
            return jsonify({
                "success": True,
                "response": cmd_result["response"],
                "command": True,
                "domain": cmd_result.get("domain", domain_for_cmd),
            })
        else:
            return jsonify({
                "success": True,
                "response": result["error"],
                "command": True,
                "domain": data.get("domain", "general"),
            })

    # Validate domain field — must match MultiDomainChatService.domains keys
    domain = data.get("domain", "general")
    valid_domains = [
        "general",
        "architecture",
        "technology",
        "business_capability",
        "gap_analysis",
        "vendor_intelligence",
        "smart_search",
        "compliance",
    ]
    is_valid, validated_domain, error = validate_enum(
        domain, valid_domains, field_name="domain", case_insensitive=True
    )
    if not is_valid:
        domain = "general"  # Default to general if invalid
    else:
        domain = validated_domain

    # Validate template_name
    template_name = data.get("template_name", "General Inquiry")
    is_valid, validated_template, error = validate_string(
        template_name, max_length=100, field_name="template_name"
    )
    if is_valid and validated_template:
        template_name = sanitize_html(validated_template)

    # Validate context element ID (optional integer)
    context_element_id = data.get("element_id")
    if context_element_id is not None:
        is_valid, validated_id, error = validate_integer(
            context_element_id, min_val=1, field_name="element_id"
        )
        if not is_valid:
            return validation_error_response(error)
        context_element_id = validated_id

    # Validate EA workflow instance ID (AIC-001: grounds chat in a specific ADM phase context)
    workflow_instance_id = data.get("instance_id")
    if workflow_instance_id is not None:
        is_valid, validated_instance_id, error = validate_integer(
            workflow_instance_id, min_val=1, field_name="instance_id"
        )
        if not is_valid:
            workflow_instance_id = None
        else:
            workflow_instance_id = validated_instance_id

    # Validate context_type
    context_type = data.get("context_type")
    if context_type:
        is_valid, validated_ctx_type, error = validate_string(
            context_type, max_length=50, field_name="context_type"
        )
        if not is_valid:
            return validation_error_response(error)
        context_type = sanitize_html(validated_ctx_type)

    # Validate solution_id — grounds chat in a specific solution context
    solution_id = data.get("solution_id")
    if solution_id is not None:
        is_valid, validated_sol_id, error = validate_integer(
            solution_id, min_val=1, field_name="solution_id"
        )
        solution_id = validated_sol_id if is_valid else None

    # AIC-312: Validate workspace_id — grounds chat in a workbench workspace
    workspace_id = data.get("workspace_id")
    if workspace_id is not None:
        is_valid, validated_ws_id, error = validate_integer(
            workspace_id, min_val=1, field_name="workspace_id"
        )
        workspace_id = validated_ws_id if is_valid else None

    # Validate persona
    persona = data.get("persona")
    if persona:
        is_valid, validated_persona, error = validate_string(
            persona, max_length=50, field_name="persona"
        )
        if not is_valid:
            return validation_error_response(error)
        persona = sanitize_html(validated_persona)

    # Validate model selection
    requested_model = data.get("model")
    if requested_model:
        is_valid, validated_model, error = validate_string(
            requested_model, max_length=100, field_name="model"
        )
        if not is_valid:
            return validation_error_response(error)
        requested_model = sanitize_html(validated_model)
        available_models = {m["model"] for m in _get_configured_chat_models()}
        if requested_model not in available_models:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "invalid_model",
                        "message": f"Model '{requested_model}' is not available.",
                    }
                ),
                400,
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

        # Inject EA workflow instance context so chat is grounded in ADM phase (AIC-001)
        if workflow_instance_id:
            context_data["instance_id"] = workflow_instance_id

        # Ground chat in a specific solution when solution_id is provided
        if solution_id:
            context_data["solution_id"] = solution_id

        # AIC-312: Ground chat in workbench workspace
        if workspace_id:
            context_data["workspace_id"] = workspace_id

        # Add document context from uploaded documents
        document_context = data.get("document_context", {})
        if document_context and isinstance(document_context, dict):
            context_data.update(document_context)

        # ENT-085: Pass attached image data for vision/multimodal analysis
        image_data = data.get("image_data")
        if image_data and isinstance(image_data, str):
            context_data["image_data"] = image_data
            context_data["image_media_type"] = data.get("image_media_type", "image/png")

        # Run AgentRunner (ReAct loop with tool use).
        # Falls back to text-only mode automatically for unsupported providers.
        from app.modules.ai_chat.services.agent_runner import AgentRunner

        runner = AgentRunner(user_id=current_user.id)
        agent_result = runner.run(
            user_message=user_message,
            domain=domain,
            context=context_data,
            persona=persona,
            requested_model=requested_model,
        )

        # ENH-018: Populate junction tables if agent result includes design_output
        if solution_id and agent_result.get("metadata", {}).get("design_output"):
            try:
                from app.modules.architecture.routes.architecture_assistant_routes import (
                    populate_solution_junctions,
                )
                populate_solution_junctions(
                    solution_id, agent_result["metadata"]["design_output"]
                )
            except Exception as _junc_err:
                logger.debug("ENH-018: Junction populate skipped: %s", _junc_err)

        return jsonify(
            {
                "success": True,
                "response": agent_result.get("response", ""),
                "domain": domain,
                "actions_taken": agent_result.get("actions_taken", []),
                "pending_approvals": agent_result.get("pending_approvals", []),
                "requires_approval": bool(agent_result.get("pending_approvals")),
                "context_used": True,
                "workspace_id": workspace_id,
                "processing_metadata": {
                    "domain": domain,
                    "persona": persona,
                    "agent_mode": True,
                },
            }
        )

    except ValueError as e:
        current_app.logger.error(f"Validation error in chat message: {str(e)}")
        return jsonify({"error": "Invalid input", "error_type": "validation"}), 400
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
        current_app.logger.error(
            f"Error processing chat message: {error_msg}", exc_info=True
        )

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


@unified_ai_chat_bp.route("/feedback", methods=["POST"])
@login_required
def submit_message_feedback():
    """Record thumbs up/down feedback on an AI message."""
    data = request.json or {}
    rating = data.get("rating")  # 'up' or 'down'
    domain = data.get("domain", "general")
    persona = data.get("persona", "")
    message_text = data.get("message_text", "")[:500]  # cap length

    if rating not in ("up", "down"):
        return jsonify({"error": "rating must be 'up' or 'down'"}), 400

    try:
        from app.extensions import db
        from sqlalchemy import text
        # Store feedback; table created lazily on first use
        _org_id = getattr(g, 'current_org_id', None)
        if _org_id:
            db.session.execute(
                text(
                    "INSERT INTO ai_chat_feedback (user_id, rating, domain, persona, message_text, created_at, organization_id) "
                    "VALUES (:uid, :r, :d, :p, :m, CURRENT_TIMESTAMP, :org_id)"
                ),
                {
                    "uid": current_user.id,
                    "r": rating,
                    "d": domain,
                    "p": persona,
                    "m": message_text,
                    "org_id": _org_id,
                },
            )
        else:
            db.session.execute(  # tenant-exempt: fallback when organization_id unavailable
                text(
                    "INSERT INTO ai_chat_feedback (user_id, rating, domain, persona, message_text, created_at) "
                    "VALUES (:uid, :r, :d, :p, :m, CURRENT_TIMESTAMP)"
                ),
                {
                    "uid": current_user.id,
                    "r": rating,
                    "d": domain,
                    "p": persona,
                    "m": message_text,
                },
            )
        db.session.commit()
    except Exception:
        # Table may not exist yet — log and return success anyway so UI works
        current_app.logger.info("ai_chat_feedback table not ready; feedback not persisted")

    return jsonify({"success": True, "rating": rating})


@unified_ai_chat_bp.route("/message/stream", methods=["POST"])
@login_required
@rate_limit(30, "1h")
def send_message_stream():
    """
    Stream a chat message via Server-Sent Events.
    Uses AgentRunner with stream_mode=True — tokens arrive as they are generated.
    Events: token | tool_start | tool_result | approval_queued | done
    """
    import queue as _queue
    import threading as _threading

    data = request.json or {}
    if not data:
        return validation_error_response("Request body is required")

    _schema = ChatMessageSchema()
    _validated, _err = _load_and_validate(_schema, data)
    if _err is not None:
        return _err
    data = _validated

    feature_guard = FeatureFlagService.require_ai_for_route(
        FeatureFlagService.FEATURE_CHAT, endpoint_name="send_message_stream"
    )
    if feature_guard:
        return feature_guard

    user_message = data.get("message", "")
    is_valid, validated_message, error = validate_chat_message(user_message)
    if not is_valid:
        return validation_error_response(error)
    user_message = validated_message

    domain = data.get("domain", "general")
    valid_domains = [
        "general", "architecture", "technology", "business_capability",
        "gap_analysis", "vendor_intelligence", "smart_search", "compliance",
    ]
    is_valid_d, validated_domain, _ = validate_enum(domain, valid_domains, case_insensitive=True)
    domain = validated_domain if is_valid_d else "general"

    persona = sanitize_html(data.get("persona") or "")
    requested_model = sanitize_html(data.get("model") or "")

    context_data = {}
    solution_id = data.get("solution_id")
    if solution_id:
        is_valid_s, validated_sol, _ = validate_integer(solution_id, min_val=1, field_name="solution_id")
        if is_valid_s:
            context_data["solution_id"] = validated_sol
    workspace_id = data.get("workspace_id")
    if workspace_id:
        is_valid_w, validated_ws, _ = validate_integer(workspace_id, min_val=1, field_name="workspace_id")
        if is_valid_w:
            context_data["workspace_id"] = validated_ws

    event_queue = _queue.Queue()

    def emit(e):
        event_queue.put(e)

    app = current_app._get_current_object()
    user_id_for_thread = current_user.id if current_user.is_authenticated else None

    def run_agent():
        try:
            with app.app_context():
                from app.modules.ai_chat.services.agent_runner import AgentRunner
                runner = AgentRunner(user_id=user_id_for_thread, yield_event=emit)
                result = runner.run(
                    user_message=user_message,
                    domain=domain,
                    context=context_data,
                    persona=persona or None,
                    requested_model=requested_model or None,
                    stream_mode=True,
                )
                event_queue.put({"type": "done", **result})
        except Exception as exc:
            logger.exception("send_message_stream: agent error")
            event_queue.put({
                "type": "done",
                "response": "",
                "error": str(exc),
                "actions_taken": [],
                "pending_approvals": [],
            })

    _threading.Thread(target=run_agent, daemon=True).start()

    def generate():
        import json as _json
        yield ": keepalive\n\n"
        while True:
            try:
                event = event_queue.get(timeout=95)
                yield f"data: {_json.dumps(event, default=str)}\n\n"
                if event.get("type") == "done":
                    break
            except _queue.Empty:
                yield ": keepalive\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _generate_follow_up_questions_simple(message: str, domain: str, persona: str) -> list:
    """Generate simple follow-up question suggestions (used by streaming endpoint)."""
    domain_qs = {
        "architecture": [
            "What ArchiMate relationships should I define?",
            "How does this align with TOGAF ADM?",
            "Which elements have the highest technical debt?",
        ],
        "technology": [
            "Which applications are at end-of-life?",
            "What integration patterns are recommended?",
            "Which applications lack a business owner?",
        ],
        "business_capability": [
            "Which capabilities have the lowest maturity?",
            "How do these map to strategic objectives?",
            "Which APQC processes are unmapped?",
        ],
        "gap_analysis": [
            "What is the remediation priority?",
            "Which gaps have highest business impact?",
            "Are there vendor solutions to close these gaps?",
        ],
        "vendor_intelligence": [
            "What is the 3-year TCO comparison?",
            "Which vendors expire in 90 days?",
            "Which vendor has the best capability fit?",
        ],
        "general": [
            "Can you give an executive summary?",
            "What are the top 3 risks to address?",
            "What should be the next step in my review?",
        ],
    }
    persona_qs = {
        "cio": ["What investment is required?", "What is the compliance risk?"],
        "enterprise_architect": [
            "How does this fit the Target Architecture?",
            "Which TOGAF deliverables should I update?",
        ],
        "business_analyst": [
            "How does this affect requirements?",
            "Which stakeholders need to be informed?",
        ],
    }
    candidates = persona_qs.get(persona, []) + domain_qs.get(domain, domain_qs["general"])
    return candidates[:3]


@unified_ai_chat_bp.route("/token-usage", methods=["GET"])
@login_required
def get_token_usage():
    """
    Get current token usage for the active chat session.
    ---
    tags:
      - AI Chat
    summary: Get token usage statistics
    description: >
        Returns estimated token count for the current user's chat history
        and the context-window limit for the active LLM provider.
    security:
      - cookieAuth: []
    responses:
      200:
        description: Token usage statistics
        schema:
          type: object
          properties:
            success:
              type: boolean
            token_usage:
              type: object
              properties:
                total_tokens:
                  type: integer
                limit:
                  type: integer
                percentage:
                  type: number
                warning:
                  type: string
            provider:
              type: string
      500:
        description: Server error
    """
    try:
        from app.modules.ai_chat.services.context_window_service import (
            ContextWindowService,
        )
        from app.services.llm_service import LLMService

        chat_service = get_chat_service()
        history = chat_service.get_chat_history(
            current_user.id if current_user.is_authenticated else None
        )

        try:
            provider_name, _ = LLMService._get_configured_provider()
        except ValueError:
            return jsonify({
                "success": True,
                "token_usage": {
                    "total_tokens": 0,
                    "limit": 0,
                    "percentage": 0,
                    "warning": "No enabled LLM provider is configured.",
                },
                "provider": None,
                "message_count": len(history),
                "configured": False,
            })

        ctx_svc = ContextWindowService()
        usage = ctx_svc.get_usage_info(history, provider_name)

        return jsonify({
            "success": True,
            "token_usage": usage,
            "provider": provider_name,
            "message_count": len(history),
            "configured": True,
        })
    except Exception as e:
        current_app.logger.error(f"Error getting token usage: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Failed to compute token usage",
        }), 500


@unified_ai_chat_bp.route("/domains", methods=["GET"])
@login_required
def get_available_domains():
    """Get available chat domains."""
    try:
        chat_service = get_chat_service()
        domains = chat_service.get_available_domains()
        return jsonify({"success": True, "domains": domains})
    except Exception as e:
        return jsonify(
            {"error": "Failed to get domains", "details": "See server logs for details"}
        ), 500


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
        return jsonify(
            {
                "error": "Failed to get personas",
                "details": "See server logs for details",
            }
        ), 500


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
        templates = AIPromptTemplate.query.all()
        template_list = []
        for template in templates:
            template_list.append(
                {
                    "id": template.id,
                    "name": template.name,
                    "description": template.description,
                    "domain": template.category,
                    "template_text": template.user_prompt_template,
                }
            )
        # ENT-056: include slash commands so the UI can surface them
        slash_commands = [
            {
                "command": "/submit-arb",
                "description": "Submit solution to ARB for review. Usage: /submit-arb <solution_id>",
            }
        ]
        return jsonify({"success": True, "templates": template_list, "slash_commands": slash_commands})
    except Exception as e:
        return jsonify(
            {
                "error": "Failed to get templates",
                "details": "See server logs for details",
            }
        ), 500


# ============================================================================
# DATA INTERACTION ROUTES (AI-DRIVEN DATA MODIFICATIONS)
# ============================================================================




# ============================================================================
# SESSION MANAGEMENT ROUTES
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
        return jsonify(
            {
                "error": "Failed to get chat history",
                "details": "See server logs for details",
            }
        ), 500


@unified_ai_chat_bp.route("/history/clear", methods=["POST"])
@login_required
@audit_log("clear_chat_history")
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
        return jsonify(
            {
                "error": "Failed to clear history",
                "details": "See server logs for details",
            }
        ), 500


@unified_ai_chat_bp.route("/session/save", methods=["POST"])
@login_required
@audit_log("save_chat_session")
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
        return jsonify(
            {
                "error": "Failed to save session",
                "details": "See server logs for details",
            }
        ), 500


@unified_ai_chat_bp.route("/sessions", methods=["GET"])
@login_required
def get_saved_sessions():
    """Get user's saved chat sessions."""
    try:
        chat_service = get_chat_service()
        sessions = chat_service.list_sessions(current_user.id)

        return jsonify({"success": True, "sessions": sessions})

    except Exception as e:
        return jsonify(
            {
                "error": "Failed to get sessions",
                "details": "See server logs for details",
            }
        ), 500


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
        return jsonify(
            {
                "error": "Failed to load session",
                "details": "See server logs for details",
            }
        ), 500


# ============================================================================
# AIC-312: WORKSPACE ENDPOINTS
# ============================================================================


@unified_ai_chat_bp.route("/workspace/<int:workspace_id>", methods=["GET"])
@login_required
def get_workspace(workspace_id):
    """Load a workbench workspace by ID."""
    from app.modules.ai_chat.services.workbench_kernel import WorkbenchKernel

    kernel = WorkbenchKernel(user_id=current_user.id)
    workspace = kernel.resume(workspace_id)

    if not workspace:
        return jsonify({"success": False, "error": "Workspace not found"}), 404

    return jsonify({"success": True, "workspace": workspace})


@unified_ai_chat_bp.route("/workspace/<int:workspace_id>/versions", methods=["GET"])
@login_required
def get_workspace_versions(workspace_id):
    """List version history for a workspace."""
    from app.modules.ai_chat.services.workbench_kernel import WorkbenchKernel

    kernel = WorkbenchKernel(user_id=current_user.id)
    workspace = kernel.load_workspace(workspace_id)
    if not workspace:
        return jsonify({"success": False, "error": "Workspace not found"}), 404

    versions = kernel.list_versions(workspace_id)
    return jsonify({"success": True, "versions": versions})


# ============================================================================
# ANALYTICS AND MONITORING
# ============================================================================




# ============================================================================
# DOMAIN CONTEXT
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
        return jsonify({"error": "An internal error occurred"}), 500


# ============================================================================
# NATURAL LANGUAGE QUERY ROUTES
# ============================================================================


# ============================================================================
# AGENT TOOL APPROVAL ROUTES
# ============================================================================


@unified_ai_chat_bp.route("/tools/approve/<int:approval_id>", methods=["POST"])
@login_required
def approve_tool_action(approval_id: int):
    """
    Execute a previously queued 'approve' tier tool action.

    The AI agent queues destructive/significant operations (e.g. update_application_status,
    submit_for_arb_review) instead of executing them immediately.  The frontend shows
    the user a confirmation dialog; clicking Confirm calls this endpoint.
    """
    from datetime import datetime
    from app import db
    from app.models.ai_chat_crud_approval import AIChatCRUDApproval, ApprovalStatus
    from app.modules.ai_chat.tools.executor import ToolCall, ToolExecutor
    import json

    record = AIChatCRUDApproval.query.get_or_404(approval_id)

    # Ownership check
    if record.user_id != current_user.id:
        return jsonify({"error": "Access denied"}), 403

    if record.status != ApprovalStatus.PENDING:
        return jsonify({"error": f"Approval is already {record.status.value}"}), 409

    # Execute
    executor = ToolExecutor(current_user.id)
    try:
        args = json.loads(record.operation_payload)
    except Exception:
        args = {}

    tc = ToolCall(id=str(approval_id), name=record.entity_type, arguments=args)
    result = executor.execute(tc)

    record.status = ApprovalStatus.APPROVED if result["success"] else ApprovalStatus.REJECTED
    record.approved_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "success": result["success"],
        "message": result.get("message", ""),
        "result": result.get("result"),
        "error": result.get("error"),
    })


@unified_ai_chat_bp.route("/tools/reject/<int:approval_id>", methods=["POST"])
@login_required
def reject_tool_action(approval_id: int):
    """Cancel a queued 'approve' tier tool action."""
    from datetime import datetime
    from app import db
    from app.models.ai_chat_crud_approval import AIChatCRUDApproval, ApprovalStatus

    record = AIChatCRUDApproval.query.get_or_404(approval_id)
    if record.user_id != current_user.id:
        return jsonify({"error": "Access denied"}), 403
    if record.status != ApprovalStatus.PENDING:
        return jsonify({"error": f"Approval is already {record.status.value}"}), 409

    record.status = ApprovalStatus.REJECTED
    record.approved_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"success": True, "message": "Action cancelled."})


@unified_ai_chat_bp.route("/session/toggle-auto-execute", methods=["POST"])
@login_required
def toggle_auto_execute():
    """
    Toggle the agent auto-execute mode for the current session.
    When ON: auto-tier tools execute immediately.
    When OFF (default): all tools queue for user confirmation.
    Returns the new state.
    """
    from flask import session as flask_session
    current = flask_session.get("agent_auto_execute", False)
    flask_session["agent_auto_execute"] = not current
    return jsonify({"success": True, "auto_execute": not current})

