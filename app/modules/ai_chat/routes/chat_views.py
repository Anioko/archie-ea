"""
Template-rendering views for the AI Chat interface.

Routes: index, document-upload, business-output, entity-matching.
Shared helper: get_chat_service().
"""

import logging
from typing import Any, Dict

from flask import current_app, render_template
from flask_login import current_user, login_required

from app.models.ai_service import AIPromptTemplate
from app.models.application_portfolio import ApplicationComponent
from app.models.business_capabilities import BusinessCapability
from app.models.unified_capability import UnifiedCapability
from app.models.vendor.vendor_organization import VendorOrganization
from app.services.multi_domain_chat_service import MultiDomainChatService
from . import unified_ai_chat_bp

logger = logging.getLogger(__name__)


def _fallback_domain_config() -> Dict[str, Dict[str, Any]]:
    """Provide a minimal, UI-safe domain config when service bootstrap fails."""
    return {
        "general": {
            "name": "General Assistant",
            "description": "Multi-Domain AI Assistant",
            "icon": "bot",
            "color": "primary",
            "expertise": ["general_inquiry", "cross_domain_analysis"],
            "templates": ["general_inquiry", "cross_domain_synthesis"],
        },
        "architecture": {
            "name": "Architecture Assistant",
            "description": "ArchiMate 3.2 Co-Pilot",
            "icon": "layers",
            "color": "blue",
            "expertise": ["enterprise_architecture", "archimate"],
            "templates": ["archimate_analysis", "element_generation"],
        },
        "technology": {
            "name": "Technology Advisor",
            "description": "Stack Analysis & Recommendations",
            "icon": "cpu",
            "color": "green",
            "expertise": ["technology_stack", "software_architecture"],
            "templates": ["tech_analysis", "stack_recommendation"],
        },
        "business_capability": {
            "name": "Capability Analyst",
            "description": "Business Capability Intelligence",
            "icon": "building-2",
            "color": "purple",
            "expertise": ["business_capabilities", "capability_mapping"],
            "templates": ["capability_analysis", "gap_assessment"],
        },
        "gap_analysis": {
            "name": "Gap Detection",
            "description": "Identify & Analyze Gaps",
            "icon": "search",
            "color": "orange",
            "expertise": ["gap_analysis", "risk_assessment"],
            "templates": ["gap_detection", "impact_analysis"],
        },
        "vendor_intelligence": {
            "name": "Vendor Intelligence",
            "description": "Vendor & Market Analysis",
            "icon": "briefcase",
            "color": "teal",
            "expertise": ["vendor_analysis", "market_research"],
            "templates": ["vendor_evaluation", "market_analysis"],
        },
        "smart_search": {
            "name": "Smart Search",
            "description": "Intelligent Search & Discovery",
            "icon": "sparkles",
            "color": "indigo",
            "expertise": ["semantic_search", "knowledge_discovery"],
            "templates": ["semantic_search", "knowledge_synthesis"],
        },
    }


def _fallback_persona_config() -> Dict[str, Any]:
    """Provide a minimal persona config when service bootstrap fails."""
    personas = MultiDomainChatService.PERSONA_CONFIGS
    return {
        "personas": personas,
        "persona_count": len(personas),
        "categories": {
            "architects": [
                "enterprise_architect",
                "solutions_architect",
                "application_architect",
                "integration_architect",
                "systems_architect",
                "business_architect",
                "data_architect",
                "technology_architect",
            ],
            "analysts": ["business_analyst", "product_analyst"],
            "executives": ["cio"],
        },
    }


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
        current_app.logger.error("Error creating chat service", exc_info=e)
        return None


# ============================================================================
# MAIN CHAT INTERFACE ROUTES
# ============================================================================



@unified_ai_chat_bp.route("/", strict_slashes=False)
@unified_ai_chat_bp.route("", strict_slashes=False)
@login_required
def index():
    """Renders the Enhanced Multi-Domain AI Chat Interface."""
    # Pre-fetch prompt templates for the UI selector (serialized for tojson in template)
    templates = []
    try:
        raw_templates = AIPromptTemplate.query.all()
        templates = [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "system_prompt": t.system_prompt,
                "user_prompt_template": t.user_prompt_template,
            }
            for t in raw_templates
        ]
    except Exception as e:
        current_app.logger.warning(f"Could not load prompt templates: {e}")

    # Keep the landing page renderable even if AI service bootstrap fails in prod.
    domain_config = _fallback_domain_config()
    persona_config = _fallback_persona_config()
    chat_bootstrap_error = None

    chat_service = get_chat_service()
    if chat_service is None:
        chat_bootstrap_error = "AI service bootstrap failed. Showing limited chat configuration."
    else:
        try:
            domain_config = chat_service.get_available_domains()
        except Exception as e:
            current_app.logger.error("Could not load AI chat domains", exc_info=e)
            chat_bootstrap_error = "AI domains could not be loaded. Showing limited chat configuration."

        try:
            persona_config = chat_service.get_available_personas()
        except Exception as e:
            current_app.logger.error("Could not load AI chat personas", exc_info=e)
            if chat_bootstrap_error is None:
                chat_bootstrap_error = "AI personas could not be loaded. Showing limited chat configuration."

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
        context_data["applications"] = ApplicationComponent.query.limit(
            context_limit
        ).all()
    except Exception as e:
        current_app.logger.warning(f"Could not load applications: {e}")

    try:
        context_data["capabilities"] = BusinessCapability.query.limit(
            context_limit
        ).all()
    except Exception as e:
        current_app.logger.warning(f"Could not load capabilities: {e}")

    try:
        context_data["vendors"] = VendorOrganization.query.limit(context_limit).all()
    except Exception as e:
        current_app.logger.warning(f"Could not load vendors: {e}")

    try:
        context_data["unified_capabilities"] = UnifiedCapability.query.limit(
            context_limit
        ).all()
    except Exception as e:
        current_app.logger.warning(f"Could not load unified capabilities: {e}")

    return render_template(
        "ai_chat/index.html",
        prompt_templates=templates,
        domain_config=domain_config,
        persona_config=persona_config,
        context_data=context_data,
        chat_bootstrap_error=chat_bootstrap_error,
    )


@unified_ai_chat_bp.route("/document-upload")
@login_required
def document_upload_view():
    """Document upload lives INSIDE the chat (floating panel). The old standalone
    route rendered a macro-only template — a blank page (UIQA-004). Redirect into
    the chat with the panel auto-opened."""
    from flask import redirect, url_for
    return redirect(url_for("unified_ai_chat.index", panel="docs"))


@unified_ai_chat_bp.route("/business-output")
@login_required
def business_output_view():
    """Stakeholder-output transformation happens in-chat on each response; the
    standalone page was an empty stub (UIQA-004). Redirect into the chat."""
    from flask import redirect, url_for
    return redirect(url_for("unified_ai_chat.index"))


@unified_ai_chat_bp.route("/entity-matching")
@login_required
def entity_matching_view():
    """Renders the Entity Matching interface for AI-powered entity resolution."""
    return render_template("ai_chat/entity_matching_chat_interface.html")


