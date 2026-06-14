"""
Solution AI Prompt Admin — allows admins to customize LLM prompts
used by the Architecture Journey.

Registered as a separate blueprint to avoid being overwritten
by deploys to admin_routes.py.
"""

import logging
from datetime import datetime

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from app.decorators import admin_required, audit_log
from app.extensions import db
from app.models.ai_service import AIPromptTemplate

logger = logging.getLogger(__name__)

solution_prompt_admin_bp = Blueprint(
    "solution_prompt_admin", __name__, url_prefix="/admin"
)

_SOLUTION_PROMPT_DEFAULTS = None


def _get_cap_suggestion_default():
    try:
        from app.modules.ai_chat.services.solution_ai_service import SolutionAIService
        return SolutionAIService.CAPABILITY_SUGGESTION_PROMPT
    except Exception:
        return "(Could not load default prompt)"


def _get_prompt_defaults():
    """Lazy-load default prompts from orchestrator class attributes."""
    global _SOLUTION_PROMPT_DEFAULTS
    if _SOLUTION_PROMPT_DEFAULTS is not None:
        return _SOLUTION_PROMPT_DEFAULTS

    from app.modules.solutions_strategic.v2.services.solution_ai_orchestrator import (
        SolutionAIOrchestrator,
    )

    _SOLUTION_PROMPT_DEFAULTS = {
        "draft_architecture": {
            "name": "Draft Architecture (Phase A)",
            "description": "Generates the complete TOGAF ADM Motivation Layer with all ArchiMate 3.2 element types.",
            "prompt_text": SolutionAIOrchestrator.DRAFT_ARCHITECTURE_PROMPT,
            "category": "Phase A",
            "variables": "solution_name, solution_type, business_domain, complexity, adm_phase, problem_statement, current_state, budget_range, timeline_months, compliance_needs, key_stakeholders, industry_context, technology_preferences, org_context",
        },
        "architecture_variants": {
            "name": "Architecture Variants",
            "description": "Produces 3 alternative architecture options: cost-optimized, timeline-optimized, and risk-balanced.",
            "prompt_text": SolutionAIOrchestrator.ARCHITECTURE_VARIANTS_PROMPT,
            "category": "Phase A",
            "variables": "solution_name, business_domain, problem_statement",
        },
        "strategy_specialist": {
            "name": "Strategy Layer (Phase B)",
            "description": "ArchiMate Strategy specialist — courses of action, value streams, capability gap analysis, resources.",
            "prompt_text": SolutionAIOrchestrator.STRATEGY_SPECIALIST_PROMPT,
            "category": "Phase B",
            "variables": "solution_name, business_domain, problem_statement, stakeholders_json, drivers_json, assessments_json, goals_json, outcomes_json, principles_json, requirements_json, constraints_json, values_json, capability_count, capabilities_json, nfr_checklist",
        },
        "business_specialist": {
            "name": "Business Layer (Phase C)",
            "description": "ArchiMate Business specialist — business actors, processes, services, roles, objects, events.",
            "prompt_text": SolutionAIOrchestrator.BUSINESS_SPECIALIST_PROMPT,
            "category": "Phase C",
            "variables": "solution_name, business_domain, stakeholders_json, drivers_json, goals_json, principles_json, constraints_json, capabilities_json, courses_of_action_json, existing_business_json, nfr_checklist, advanced_business_schema",
        },
        "application_specialist": {
            "name": "Application Layer (Phase C)",
            "description": "ArchiMate Application specialist — application components, services, data objects, interfaces.",
            "prompt_text": SolutionAIOrchestrator.APPLICATION_SPECIALIST_PROMPT,
            "category": "Phase C",
            "variables": "solution_name, business_domain, requirements_json, principles_json, constraints_json, capabilities_json, business_services_json, app_count, existing_apps_json, nfr_checklist",
        },
        "technology_specialist": {
            "name": "Technology Layer (Phase D)",
            "description": "ArchiMate Technology specialist — nodes, system software, technology services, networks, artifacts.",
            "prompt_text": SolutionAIOrchestrator.TECHNOLOGY_SPECIALIST_PROMPT,
            "category": "Phase D",
            "variables": "solution_name, business_domain, tech_preferences, constraints_json, principles_json, app_components_json, existing_infra_json, nfr_checklist",
        },
        "implementation_specialist": {
            "name": "Implementation & Migration (Phase F)",
            "description": "TOGAF Phase F Migration Planning — plateaus, gaps, work packages, deliverables, milestones.",
            "prompt_text": SolutionAIOrchestrator.IMPLEMENTATION_SPECIALIST_PROMPT,
            "category": "Phase F",
            "variables": "solution_name, business_domain, timeline_constraint, budget_constraint, goals_json, stakeholders_json, principles_json, gaps_json, capabilities_json, plateaus_json, nfr_checklist",
        },
        "capability_suggestion": {
            "name": "Capability Suggestions (Step 2)",
            "description": "Maps business problems to APQC capabilities — suggests which capabilities a solution should address.",
            "prompt_text": _get_cap_suggestion_default(),
            "category": "Step 2",
            "variables": "solution_description, solution_type, business_domain, capability_catalog",
        },
        "codegen_uml_enrichment": {
            "name": "UML Enrichment (Code Workbench)",
            "description": "Transforms ArchiMate elements into UML class, sequence, component, and deployment diagrams for code generation.",
            "prompt_text": _get_codegen_prompt("uml_enrichment_service", "UML_ENRICHMENT_PROMPT"),
            "category": "Code Workbench",
            "variables": "data_objects_json, app_interfaces_json, app_components_json, app_services_json, business_processes_json, tech_nodes_json, requirements_json, constraints_json",
        },
        "codegen_models": {
            "name": "Code Generation: Models",
            "description": "Generates SQLAlchemy 2.0 model files from UML class diagram.",
            "prompt_text": _get_codegen_prompt("code_generation_service", "PROMPTS", "models"),
            "category": "Code Workbench",
            "variables": "class_diagram_json, python_version, auth_type",
        },
        "codegen_schemas": {
            "name": "Code Generation: Schemas",
            "description": "Generates Pydantic v2 schemas (Create/Update/Response) from UML class diagram.",
            "prompt_text": _get_codegen_prompt("code_generation_service", "PROMPTS", "schemas"),
            "category": "Code Workbench",
            "variables": "class_diagram_json",
        },
        "codegen_routes": {
            "name": "Code Generation: Routes",
            "description": "Generates FastAPI route handlers with full CRUD operations.",
            "prompt_text": _get_codegen_prompt("code_generation_service", "PROMPTS", "routes"),
            "category": "Code Workbench",
            "variables": "sequence_diagram_json, class_diagram_json, auth_type",
        },
        "codegen_services": {
            "name": "Code Generation: Services",
            "description": "Generates service layer classes with business logic from component diagram.",
            "prompt_text": _get_codegen_prompt("code_generation_service", "PROMPTS", "services"),
            "category": "Code Workbench",
            "variables": "component_diagram_json, sequence_diagram_json",
        },
        "codegen_integrations": {
            "name": "Code Generation: Integrations",
            "description": "Generates typed Protocol interfaces for external system integrations.",
            "prompt_text": _get_codegen_prompt("code_generation_service", "PROMPTS", "integrations"),
            "category": "Code Workbench",
            "variables": "external_interfaces_json",
        },
        "codegen_tests": {
            "name": "Code Generation: Tests",
            "description": "Generates pytest test files with CRUD test cases for all routes.",
            "prompt_text": _get_codegen_prompt("code_generation_service", "PROMPTS", "tests"),
            "category": "Code Workbench",
            "variables": "routes_summary_json, class_diagram_json",
        },
        "codegen_infrastructure": {
            "name": "Code Generation: Infrastructure",
            "description": "Generates Dockerfile, docker-compose.yml, requirements.txt, and config files.",
            "prompt_text": _get_codegen_prompt("code_generation_service", "PROMPTS", "infrastructure"),
            "category": "Code Workbench",
            "variables": "deployment_diagram_json, python_version",
        },
    }
    return _SOLUTION_PROMPT_DEFAULTS


def _get_codegen_prompt(module_name, attr_name, key=None):
    """Load a codegen prompt default from the service modules."""
    try:
        if module_name == "uml_enrichment_service":
            from app.modules.codegen.services.uml_enrichment_service import UML_ENRICHMENT_PROMPT
            return UML_ENRICHMENT_PROMPT
        elif module_name == "code_generation_service":
            from app.modules.codegen.services.code_generation_service import PROMPTS
            return PROMPTS.get(key, "(prompt not found)")
    except Exception as exc:
        logger.debug("Could not load codegen prompt default: %s", exc)
    return "(Could not load default prompt)"


def _override_key(prompt_key):
    return f"solution_prompt_{prompt_key}"


@solution_prompt_admin_bp.route("/solution-prompts")
@login_required
@admin_required
def solution_prompts_page():
    """Render the solution AI prompt management page."""
    return render_template("admin/solution_prompts.html")


@solution_prompt_admin_bp.route("/solution-prompts/data")
@login_required
@admin_required
def solution_prompts_data():
    """JSON API: return all solution prompt configs merged with DB overrides."""
    defaults = _get_prompt_defaults()
    prompts = []

    for key, config in defaults.items():
        override_name = _override_key(key)
        override = AIPromptTemplate.query.filter_by(name=override_name).first()

        prompts.append({
            "key": key,
            "name": config["name"],
            "description": config["description"],
            "category": config["category"],
            "variables": config["variables"],
            "default_prompt": config["prompt_text"],
            "current_prompt": override.system_prompt if override else config["prompt_text"],
            "has_override": override is not None,
        })

    return jsonify({"prompts": prompts})


@solution_prompt_admin_bp.route("/solution-prompts/<prompt_key>/update", methods=["POST"])
@login_required
@admin_required
@audit_log("update_solution_prompt")
def solution_prompt_update(prompt_key):
    """Save a custom override for a solution prompt."""
    defaults = _get_prompt_defaults()
    if prompt_key not in defaults:
        return jsonify({"error": f"Unknown prompt: {prompt_key}"}), 404

    payload = request.get_json(silent=True) or {}
    prompt_text = (payload.get("prompt_text") or "").strip()

    if not prompt_text:
        return jsonify({"error": "Prompt text cannot be empty"}), 400

    override_name = _override_key(prompt_key)
    override = AIPromptTemplate.query.filter_by(name=override_name).first()

    if not override:
        override = AIPromptTemplate(
            name=override_name,
            description=defaults[prompt_key]["description"],
            system_prompt=prompt_text,
            user_prompt_template="",
            category="solution_prompt",
        )
        db.session.add(override)
    else:
        override.system_prompt = prompt_text
        override.updated_at = datetime.utcnow()

    try:
        db.session.commit()
        logger.info("Solution prompt override saved for %s by user %s", prompt_key, current_user.id)
    except Exception:
        db.session.rollback()
        logger.exception("Failed to save solution prompt override for %s", prompt_key)
        return jsonify({"error": "Database error saving override"}), 500

    config = defaults[prompt_key]
    return jsonify({
        "success": True,
        "prompt": {
            "key": prompt_key,
            "name": config["name"],
            "description": config["description"],
            "category": config["category"],
            "variables": config["variables"],
            "default_prompt": config["prompt_text"],
            "current_prompt": override.system_prompt,
            "has_override": True,
        },
    })


@solution_prompt_admin_bp.route("/solution-prompts/<prompt_key>/reset", methods=["POST"])
@login_required
@admin_required
@audit_log("reset_solution_prompt")
def solution_prompt_reset(prompt_key):
    """Remove custom override, reverting to hardcoded default."""
    defaults = _get_prompt_defaults()
    if prompt_key not in defaults:
        return jsonify({"error": f"Unknown prompt: {prompt_key}"}), 404

    override_name = _override_key(prompt_key)
    override = AIPromptTemplate.query.filter_by(name=override_name).first()

    if override:
        try:
            db.session.delete(override)
            db.session.commit()
            logger.info("Solution prompt override reset for %s by user %s", prompt_key, current_user.id)
        except Exception:
            db.session.rollback()
            logger.exception("Failed to reset solution prompt for %s", prompt_key)
            return jsonify({"error": "Database error resetting prompt"}), 500

    config = defaults[prompt_key]
    return jsonify({
        "success": True,
        "prompt": {
            "key": prompt_key,
            "name": config["name"],
            "description": config["description"],
            "category": config["category"],
            "variables": config["variables"],
            "default_prompt": config["prompt_text"],
            "current_prompt": config["prompt_text"],
            "has_override": False,
        },
    })
