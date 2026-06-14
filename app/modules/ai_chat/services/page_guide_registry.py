"""
Registry for the page-aware AI guide.
"""

from copy import deepcopy
from typing import Any, Dict, Optional

from flask import url_for


_BASE_ENTRIES = {
    "dashboard.overview": {
        "page_key": "dashboard.overview",
        "title": "Dashboard overview",
        "summary": (
            "This page gives you a quick orientation to the platform. Use it to "
            "review platform status, jump to major modules, and decide what to do next."
        ),
        "starter_questions": [
            "What should I do first on this platform?",
            "Which area should I use for my role?",
            "What are the main workflows available from here?",
        ],
        "glossary": [
            {
                "term": "Quick Access",
                "definition": "Shortcut cards that open key modules and common workflows.",
            },
            {
                "term": "Feature Directory",
                "definition": "An overview of platform capabilities grouped by function.",
            },
        ],
        "suggested_actions": [
            {
                "label": "Open applications",
                "description": "Review the application portfolio.",
                "endpoint": "unified_applications.application_list",
            },
            {
                "label": "Open solutions",
                "description": "Browse or continue solution work.",
                "endpoint": "solution_design.list_solutions",
            },
        ],
    },
    "applications.list": {
        "page_key": "applications.list",
        "title": "Applications portfolio",
        "summary": (
            "This page lists application portfolio records. Use filters, search, "
            "and portfolio stats to find systems and decide which application to inspect."
        ),
        "starter_questions": [
            "How do I find a specific application quickly?",
            "What do the portfolio stats tell me?",
            "When should I open an application detail page?",
        ],
        "glossary": [
            {
                "term": "Portfolio stats",
                "definition": "Summary counts for the application estate, such as critical or retired systems.",
            },
            {
                "term": "Filters",
                "definition": "Controls that narrow the list by status, type, domain, or search text.",
            },
        ],
        "suggested_actions": [
            {
                "label": "Back to dashboard",
                "description": "Return to the main overview.",
                "endpoint": "dashboard.overview",
            },
        ],
    },
    "applications.detail": {
        "page_key": "applications.detail",
        "title": "Application detail",
        "summary": (
            "This page shows one application's architecture, relationships, and supporting data. "
            "Use it to understand the system before making changes elsewhere."
        ),
        "starter_questions": [
            "What should I look at first on this application page?",
            "How do I interpret the architecture information here?",
            "What are the safest next steps from this page?",
        ],
        "glossary": [
            {
                "term": "Architecture tab",
                "definition": "The main area for reviewing structural information about the application.",
            },
            {
                "term": "Relationships",
                "definition": "Links from the application to capabilities, vendors, data, and related elements.",
            },
        ],
        "suggested_actions": [
            {
                "label": "Open applications list",
                "description": "Return to the portfolio view.",
                "endpoint": "unified_applications.application_list",
            },
        ],
    },
    "solutions.list": {
        "page_key": "solutions.list",
        "title": "Solutions list",
        "summary": (
            "This page lets you browse, filter, and continue enterprise solution work. "
            "Use it to review status, ownership, and which solution to open next."
        ),
        "starter_questions": [
            "How do I know which solution to open first?",
            "What do the solution status values mean?",
            "When should I create a new solution instead of editing an existing one?",
        ],
        "glossary": [
            {
                "term": "Solution status",
                "definition": "Lifecycle state such as planned, in progress, or deployed.",
            },
            {
                "term": "Business domain",
                "definition": "The business area that the solution primarily supports.",
            },
        ],
        "suggested_actions": [
            {
                "label": "Back to dashboard",
                "description": "Return to the main overview.",
                "endpoint": "dashboard.overview",
            },
        ],
    },
    "solutions.detail": {
        "page_key": "solutions.detail",
        "title": "Solution detail",
        "summary": (
            "This page holds the working detail for a single solution. Use it to "
            "review architecture, delivery, risks, and supporting sections before editing."
        ),
        "starter_questions": [
            "What sections matter most on a solution detail page?",
            "How should I review this solution before editing it?",
            "What is the recommended next step from here?",
        ],
        "glossary": [
            {
                "term": "SAD",
                "definition": "Solution Architecture Document content captured across the solution detail sections.",
            },
            {
                "term": "Risk and delivery",
                "definition": "Sections that explain implementation constraints, governance, and rollout readiness.",
            },
        ],
        "suggested_actions": [
            {
                "label": "Open solutions list",
                "description": "Return to all solutions.",
                "endpoint": "solution_design.list_solutions",
            },
        ],
    },
    "archimate.composer": {
        "page_key": "archimate.composer",
        "title": "ArchiMate Composer",
        "summary": (
            "The ArchiMate Composer is your diagramming workspace for creating and editing "
            "architecture views. Drag elements from the palette, connect them with ArchiMate "
            "relationships, and save viewpoints for review and collaboration."
        ),
        "starter_questions": [
            "How do I create a new architecture diagram?",
            "What ArchiMate relationship types can I use?",
            "How do I export my diagram for a presentation?",
            "What are the different ArchiMate viewpoints?",
        ],
        "glossary": [
            {"term": "Viewpoint", "definition": "A saved diagram configuration showing elements and relationships from a specific perspective (e.g., Application Cooperation, Technology)."},
            {"term": "Layer", "definition": "ArchiMate organises elements into layers: Business, Application, Technology, Motivation, Strategy, Implementation & Migration, and Physical."},
            {"term": "Relationship", "definition": "A typed connection between elements such as Serving, Realization, Composition, Flow, or Association."},
            {"term": "Grouping", "definition": "A container element used to visually group related elements, often representing deployment zones (SaaS, On-Prem, Azure)."},
        ],
        "suggested_actions": [
            {"label": "Architecture Models", "description": "Browse all saved architecture models.", "endpoint": "architect_ui.architecture_models"},
            {"label": "Open solutions", "description": "Browse solution designs.", "endpoint": "solution_design.list_solutions"},
        ],
    },
    "architecture_journey": {
        "page_key": "architecture_journey",
        "title": "Architecture Journey",
        "summary": (
            "The Architecture Journey guides you through creating a solution design step by step. "
            "Define your problem, review ACM domain proposals across 7 capability areas, generate "
            "architecture blueprints, and progress through TOGAF ADM phases."
        ),
        "starter_questions": [
            "What are the 7 ACM domains I need to address?",
            "How do I confirm a domain and promote elements?",
            "What does the property coverage percentage mean?",
            "How do I progress from Step 2 to Step 3?",
        ],
        "glossary": [
            {"term": "ACM Domain", "definition": "Application Capability Model domain — one of 7 areas: UX, APP, DATA, SEC, DEV, AI, COM. Each solution must address all 7."},
            {"term": "Differentiating", "definition": "A domain tier indicating high strategic importance. Requires 80%+ property coverage and NFR compliance before proceeding."},
            {"term": "NFR", "definition": "Non-Functional Requirement — quality attributes like performance, security, and availability that must be addressed for each domain."},
            {"term": "Property Coverage", "definition": "Percentage of required element properties that have been filled. Higher tiers require higher coverage."},
        ],
        "suggested_actions": [
            {"label": "Open solutions", "description": "View all solution designs.", "endpoint": "solution_design.list_solutions"},
            {"label": "Capability Health", "description": "Review capability maturity.", "endpoint": "capability_map.simple_view"},
        ],
    },
    "vendor.list": {
        "page_key": "vendor.list",
        "title": "Vendor Management",
        "summary": (
            "Manage your vendor portfolio — view vendor organisations, their products, "
            "contracts, and relationships to applications in your enterprise architecture."
        ),
        "starter_questions": [
            "How do I add a new vendor?",
            "How are vendors linked to applications?",
            "What vendor data comes from Abacus?",
        ],
        "glossary": [
            {"term": "Vendor", "definition": "An external organisation that provides products or services used by the enterprise."},
            {"term": "Product", "definition": "A specific offering from a vendor, linked to one or more applications."},
        ],
        "suggested_actions": [
            {"label": "Open applications", "description": "Review application portfolio.", "endpoint": "unified_applications.application_list"},
        ],
    },
    "capability_map": {
        "page_key": "capability_map",
        "title": "Capability Health",
        "summary": (
            "View and manage business capabilities and their maturity. Capabilities are "
            "organised in a hierarchy and linked to applications, solutions, and ArchiMate elements."
        ),
        "starter_questions": [
            "What is a capability and how is it different from an application?",
            "How do I assess capability maturity?",
            "How are capabilities linked to the ACM domains?",
        ],
        "glossary": [
            {"term": "Capability", "definition": "A business ability that the organisation needs, independent of how it is implemented."},
            {"term": "Maturity", "definition": "A score indicating how well a capability is supported by technology and processes."},
        ],
        "suggested_actions": [
            {"label": "Open applications", "description": "See which applications support capabilities.", "endpoint": "unified_applications.application_list"},
        ],
    },
    "rationalization": {
        "page_key": "rationalization",
        "title": "Application Rationalization",
        "summary": (
            "Analyse your application portfolio to identify redundancies, gaps, and "
            "retirement candidates. Each application is scored based on lifecycle, cost, "
            "risk, usage, and strategic alignment."
        ),
        "starter_questions": [
            "How is the rationalization score calculated?",
            "What does 'insufficient evidence' mean for an app score?",
            "How do I identify applications for retirement?",
        ],
        "glossary": [
            {"term": "Rationalization Score", "definition": "A weighted score (0-100) combining lifecycle status, cost, risk, usage, and vendor health."},
            {"term": "TIME Classification", "definition": "Tolerate, Invest, Migrate, Eliminate — the standard rationalization categories."},
        ],
        "suggested_actions": [
            {"label": "Open applications", "description": "Review detailed application data.", "endpoint": "unified_applications.application_list"},
        ],
    },
    # PLT-040: Additional page guide entries for key pages
    "archimate_crud.dashboard": {
        "page_key": "archimate_crud.dashboard",
        "title": "ArchiMate Elements",
        "summary": (
            "Browse, filter, and manage ArchiMate elements in the enterprise architecture catalog. "
            "Each element represents a building block — applications, services, processes, or technology."
        ),
        "starter_questions": [
            "How do I create a new ArchiMate element?",
            "What element types are available?",
            "How do I link elements to solutions?",
        ],
        "glossary": [
            {"term": "ArchiMate", "definition": "An open standard for enterprise architecture modeling (The Open Group)."},
            {"term": "Element", "definition": "A single architecture building block — e.g., an Application Component or Business Service."},
            {"term": "Relationship", "definition": "A typed link between two elements, such as 'serves', 'realizes', or 'composes'."},
        ],
        "suggested_actions": [
            {"label": "Open Composer", "description": "Create elements visually.", "endpoint": "archimate.composer_page"},
            {"label": "View solutions", "description": "See solution designs that use these elements.", "endpoint": "solution_design.list_solutions"},
        ],
    },
    "arb.dashboard": {
        "page_key": "arb.dashboard",
        "title": "Architecture Review Board",
        "summary": (
            "Review and vote on architecture submissions. The ARB ensures solution designs "
            "comply with standards, principles, and governance policies before implementation."
        ),
        "starter_questions": [
            "What submissions are waiting for review?",
            "How do I approve or reject a submission?",
            "What governance criteria should I check?",
        ],
        "glossary": [
            {"term": "ARB", "definition": "Architecture Review Board — a governance body that reviews and approves architecture decisions."},
            {"term": "Submission", "definition": "A solution design document submitted for architecture review and approval."},
        ],
        "suggested_actions": [
            {"label": "View solutions", "description": "Browse solution designs.", "endpoint": "solution_design.list_solutions"},
            {"label": "Governance gates", "description": "Manage governance checkpoints.", "endpoint": "admin.governance_gates"},
        ],
    },
    "adm_kanban": {
        "page_key": "adm_kanban",
        "title": "ADM Kanban Board",
        "summary": (
            "Track solution progress through TOGAF ADM phases on a visual kanban board. "
            "Drag cards between phases to update solution status."
        ),
        "starter_questions": [
            "How do I move a solution to the next phase?",
            "What do the ADM phases mean?",
            "How do I filter by solution owner?",
        ],
        "glossary": [
            {"term": "ADM", "definition": "Architecture Development Method — TOGAF's iterative approach to enterprise architecture."},
            {"term": "Phase", "definition": "One of 8 ADM phases (A-H), from Architecture Vision through Change Management."},
        ],
        "suggested_actions": [
            {"label": "Architecture Journey", "description": "Create a new solution via the guided wizard.", "endpoint": "architecture_journey.index"},
        ],
    },
    "governance.dashboard": {
        "page_key": "governance.dashboard",
        "title": "Governance Dashboard",
        "summary": (
            "Monitor architecture governance status, compliance scores, and review pipelines. "
            "Use this to identify solutions that need governance attention."
        ),
        "starter_questions": [
            "Which solutions need governance review?",
            "How are governance gates configured?",
            "What is the overall compliance posture?",
        ],
        "glossary": [
            {"term": "Governance gate", "definition": "A checkpoint that blocks or allows progression based on compliance criteria."},
        ],
        "suggested_actions": [
            {"label": "ARB dashboard", "description": "Review pending submissions.", "endpoint": "arb.dashboard"},
            {"label": "Solutions list", "description": "Browse all solutions.", "endpoint": "solution_design.list_solutions"},
        ],
    },
    "health_scorecard": {
        "page_key": "health_scorecard",
        "title": "Health Scorecard",
        "summary": (
            "Monitor platform data quality and architecture health metrics. "
            "The scorecard shows data coverage, element completeness, and portfolio health."
        ),
        "starter_questions": [
            "What does the health score measure?",
            "How can I improve data coverage?",
            "What areas need the most attention?",
        ],
        "glossary": [
            {"term": "Health score", "definition": "A weighted composite of phase maturity, risk, capability coverage, and governance metrics."},
            {"term": "Data coverage", "definition": "Percentage of application fields populated (owner, vendor, cost, risk, criticality)."},
        ],
        "suggested_actions": [
            {"label": "Dashboard overview", "description": "Return to the main dashboard.", "endpoint": "dashboard.overview"},
            {"label": "Applications", "description": "Improve data quality on applications.", "endpoint": "unified_applications.application_list"},
        ],
    },
    "codegen.workbench": {
        "page_key": "codegen.workbench",
        "title": "Code Workbench",
        "summary": (
            "Generate, review, and refine production-ready code from a solution blueprint. "
            "The workbench scores quality, checks blueprint violations, runs invariant tests, "
            "and streams code generation."
        ),
        "starter_questions": [
            "How do I start code generation for this solution?",
            "What are blueprint violations and how do I fix them?",
            "How do invariant tests work in the workbench?",
            "Can I regenerate only part of the code?",
        ],
        "glossary": [
            {"term": "Blueprint violation", "definition": "A pattern in the generated code that breaks the architectural constraints defined in the solution blueprint."},
            {"term": "Invariant test", "definition": "An auto-generated assertion that verifies the generated code obeys its own declared contracts."},
            {"term": "Quality score", "definition": "A composite measure of code completeness, coverage, and alignment with the solution's ArchiMate model."},
        ],
        "suggested_actions": [
            {"label": "View solution", "description": "Return to the solution detail.", "endpoint": "solution_design.view_solution"},
            {"label": "Solutions list", "description": "Browse all solutions.", "endpoint": "solution_design.list_solutions"},
        ],
    },
    "ai_chat": {
        "page_key": "ai_chat",
        "title": "AI Architect Chat",
        "summary": (
            "Chat with an AI architecture assistant that knows your portfolio. "
            "Use domain-specific modes (Architecture, Applications, Greenfield, Brownfield) "
            "and start structured workflows directly from this page."
        ),
        "starter_questions": [
            "What can I do from this chat page?",
            "How do I start a greenfield blueprint workflow?",
            "What domains are available in this chat?",
            "How does the chat differ from the Journey Wizard?",
        ],
        "glossary": [
            {"term": "Domain mode", "definition": "A pre-configured context (e.g., Applications, Architecture) that focuses the AI on a specific area of the platform."},
            {"term": "Greenfield workflow", "definition": "A structured 7-step conversation that produces a full solution blueprint from a business brief."},
            {"term": "Brownfield workflow", "definition": "A structured 6-step conversation that assesses your current portfolio and produces a modernization plan."},
        ],
        "suggested_actions": [
            {"label": "Solutions list", "description": "Browse or create solutions.", "endpoint": "solution_design.list_solutions"},
            {"label": "Dashboard", "description": "Return to the platform overview.", "endpoint": "dashboard.overview"},
        ],
    },
    "admin.generic": {
        "page_key": "admin.generic",
        "title": "Platform guide",
        "summary": (
            "This page does not yet have specialized AI guide content. "
            "Use the guide for safe orientation, navigation help, and the next best platform page to open."
        ),
        "starter_questions": [
            "What is this page generally used for?",
            "What should I check before making changes here?",
            "Where should I go next for architecture work?",
        ],
        "glossary": [
            {
                "term": "Specialized guide",
                "definition": "A page-specific guide with metadata tailored to a known workflow or detail view.",
            },
            {
                "term": "General guide",
                "definition": "A safe fallback mode that helps you orient yourself without inventing page-specific behavior.",
            },
        ],
        "suggested_actions": [
            {
                "label": "Open dashboard",
                "description": "Return to the main platform overview.",
                "endpoint": "dashboard.overview",
            },
            {
                "label": "Open applications",
                "description": "Review the application portfolio.",
                "endpoint": "unified_applications.application_list",
            },
            {
                "label": "Open solutions",
                "description": "Browse or continue solution work.",
                "endpoint": "solution_design.list_solutions",
            },
        ],
    },
}


def resolve_page_guide(endpoint: Optional[str], view_args: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Resolve the current endpoint to a guide entry."""
    if not endpoint:
        return None

    view_args = view_args or {}
    page_key = None
    scope_value = None

    if endpoint in {"dashboard.overview", "dashboard_v2.overview"}:
        page_key = "dashboard.overview"  # secrets-safety-ok: page guide key, not a secret
    elif endpoint == "unified_applications.application_list":
        page_key = "applications.list"  # secrets-safety-ok: page guide key, not a secret
    elif endpoint == "unified_applications.application_detail":
        page_key = "applications.detail"  # secrets-safety-ok: page guide key, not a secret
        scope_value = view_args.get("id")
    elif endpoint == "solution_design.list_solutions":
        page_key = "solutions.list"
    elif endpoint == "solution_design.view_solution":
        page_key = "solutions.detail"  # secrets-safety-ok: page guide key, not a secret
        scope_value = view_args.get("solution_id")

    elif endpoint in {"archimate.composer_page", "architect_ui.composer"}:
        page_key = "archimate.composer"  # secrets-safety-ok: page guide key, not a secret
    elif endpoint in {"architecture_journey.journey_page", "architecture_journey.index"}:
        page_key = "architecture_journey"  # secrets-safety-ok: page guide key, not a secret
        scope_value = view_args.get("solution_id")
    elif endpoint in {"unified_applications.vendors"}:
        page_key = "vendor.list"  # secrets-safety-ok: page guide key, not a secret
    elif endpoint in {"strategic.capability_health", "capability_map.simple_view"}:
        page_key = "capability_map"  # secrets-safety-ok: page guide key, not a secret
    elif endpoint in {"unified_applications.rationalization_dashboard"}:
        page_key = "rationalization"  # secrets-safety-ok: page guide key, not a secret
    elif endpoint in {"dashboard.health_scorecard"}:
        page_key = "health_scorecard"  # secrets-safety-ok: PLT-040 dedicated entry
    elif endpoint in {"strategic.impact_analysis"}:
        page_key = "admin.generic"  # secrets-safety-ok: fallback
    elif endpoint in {"adm_kanban_view.index"}:
        page_key = "adm_kanban"  # secrets-safety-ok: PLT-040 dedicated entry
    elif endpoint in {"archimate_crud.dashboard"}:
        page_key = "archimate_crud.dashboard"  # secrets-safety-ok: PLT-040 dedicated entry
    elif endpoint in {"arb.dashboard"}:
        page_key = "arb.dashboard"  # secrets-safety-ok: PLT-040 dedicated entry
    elif endpoint in {"capability_governance.governance_dashboard"}:
        page_key = "governance.dashboard"  # secrets-safety-ok: PLT-040 dedicated entry
    elif endpoint in {"architecture_journey.index"}:
        page_key = "solutions.list"  # secrets-safety-ok: reuse solutions guide
    elif endpoint in {"main.ea_workflows_dashboard"}:
        page_key = "admin.generic"  # secrets-safety-ok: fallback
    elif endpoint in {"codegen.workbench_page"}:
        page_key = "codegen.workbench"  # secrets-safety-ok: page guide key
        scope_value = view_args.get("solution_id")
    elif endpoint in {"unified_ai_chat.index", "unified_ai_chat.legacy_chat_index"}:
        page_key = "ai_chat"  # secrets-safety-ok: page guide key
    elif endpoint in {"strategic_routes.roadmap_index"}:
        page_key = "admin.generic"  # secrets-safety-ok: fallback until dedicated entry added

    if not page_key:
        return None

    entry = deepcopy(_BASE_ENTRIES[page_key])
    entry["guide_mode"] = "specialized"
    if scope_value is not None:
        entry["scope_key"] = f"{page_key}:{scope_value}"
        entry["scope_value"] = scope_value
    else:
        entry["scope_key"] = page_key
        entry["scope_value"] = None

    entry["endpoint"] = endpoint
    entry["suggested_actions"] = _materialize_actions(entry["suggested_actions"], view_args)
    return entry


def get_entry_for_page_key(page_key: str) -> Optional[Dict[str, Any]]:
    """Get a static registry entry by page key."""
    entry = _BASE_ENTRIES.get(page_key)
    return deepcopy(entry) if entry else None


def build_generic_page_guide(
    endpoint: Optional[str],
    view_args: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a bounded fallback guide for authenticated pages without a specialized entry."""
    view_args = view_args or {}
    entry = deepcopy(_BASE_ENTRIES["admin.generic"])
    page_label = _humanize_endpoint(endpoint)
    entry["guide_mode"] = "generic"
    entry["endpoint"] = endpoint
    entry["title"] = f"{page_label} guide"
    entry["scope_key"] = f"admin.generic:{endpoint or 'unknown'}"
    entry["scope_value"] = endpoint
    entry["suggested_actions"] = _materialize_actions(entry["suggested_actions"], view_args)
    return entry


def _humanize_endpoint(endpoint: Optional[str]) -> str:
    if not endpoint:
        return "Platform"

    label = endpoint.split(".")[-1].replace("_", " ").strip()
    if not label:
        return "Platform"
    return label[:1].upper() + label[1:]


def _materialize_actions(actions, view_args: Dict[str, Any]) -> list:
    materialized = []
    for action in actions:
        item = deepcopy(action)
        endpoint = item.pop("endpoint", None)
        route_args = deepcopy(item.pop("route_args", {}))
        for key, value in list(route_args.items()):
            if isinstance(value, str) and value.startswith("$"):
                route_args[key] = view_args.get(value[1:])
        if endpoint:
            try:
                item["url"] = url_for(endpoint, **route_args)
            except Exception:
                item["url"] = "#"
        materialized.append(item)
    return materialized
