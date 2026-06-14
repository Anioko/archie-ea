"""
API Registry - Single Source of Truth for All API Endpoints

This registry documents all Flask blueprints, their URL prefixes, and endpoints.
Use this for API discovery, health checks, and consolidation planning.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class BlueprintStatus(Enum):
    """Blueprint status for consolidation tracking"""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    CONSOLIDATED = "consolidated"
    LEGACY = "legacy"


@dataclass
class APIEndpoint:
    """Individual API endpoint definition"""

    path: str
    methods: List[str]
    auth_required: bool
    description: str


@dataclass
class BlueprintInfo:
    """Blueprint registration information"""

    name: str
    module: str
    url_prefix: str
    status: BlueprintStatus
    endpoints_count: int
    legacy_prefixes: Optional[List[str]] = None
    consolidate_into: Optional[str] = None
    notes: Optional[str] = None


# ============================================================================
# COMPLETE API REGISTRY
# ============================================================================

API_REGISTRY: Dict[str, BlueprintInfo] = {
    # ========================================================================
    # CORE APPLICATION BLUEPRINTS
    # ========================================================================
    "main": BlueprintInfo(
        name="main",
        module="app.main",
        url_prefix="/",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=5,
        notes="Main landing pages and core routes",
    ),
    "account": BlueprintInfo(
        name="account",
        module="app.account",
        url_prefix="/account",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=8,
        notes="User authentication and account management",
    ),
    "admin": BlueprintInfo(
        name="admin",
        module="app.admin",
        url_prefix="/admin",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=12,
        notes="Admin dashboard and settings",
    ),
    # ========================================================================
    # APPLICATION MANAGEMENT - CONSOLIDATION TARGET
    # ========================================================================
    "unified_applications": BlueprintInfo(
        name="unified_applications",
        module="app.routes.unified_applications_routes",
        url_prefix="/applications",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=25,
        notes="PRIMARY applications blueprint - feature complete",
    ),
    "application_mgmt": BlueprintInfo(
        name="application_mgmt",
        module="app.application_mgmt",
        url_prefix="/dashboard",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=30,
        notes="Dashboard APIs and CRUD operations",
        consolidate_into="unified_applications",
    ),
    "streaming_import": BlueprintInfo(
        name="streaming_import",
        module="app.routes.streaming_import_routes",
        url_prefix="/applications",
        status=BlueprintStatus.DEPRECATED,
        endpoints_count=3,
        notes="Import functionality - merge into unified_applications",
        consolidate_into="unified_applications",
    ),
    # ========================================================================
    # VENDOR MANAGEMENT - CONSOLIDATION TARGET
    # ========================================================================
    "vendors_api": BlueprintInfo(
        name="vendors_api",
        module="app.api_vendors",
        url_prefix="/api/vendors",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=15,
        notes="PRIMARY vendor API with Flask-RESTX and Swagger",
    ),
    "vendors": BlueprintInfo(
        name="vendors",
        module="app.vendors",
        url_prefix="/vendors",
        status=BlueprintStatus.DEPRECATED,
        endpoints_count=8,
        notes="Legacy vendor routes - consolidate into vendors_api",
        consolidate_into="vendors_api",
    ),
    "enhanced_vendor": BlueprintInfo(
        name="enhanced_vendor",
        module="app.api.enhanced_vendor_api",
        url_prefix="/api/enhanced-vendor",
        status=BlueprintStatus.DEPRECATED,
        endpoints_count=10,
        notes="Enhanced features - merge into vendors_api",
        consolidate_into="vendors_api",
    ),
    # ========================================================================
    # DUPLICATE DETECTION - UNIFIED SYSTEM
    # ========================================================================
    "unified_duplicate": BlueprintInfo(
        name="unified_duplicate",
        module="app.routes.unified_duplicate_routes",
        url_prefix="/duplicate-detection",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=20,
        legacy_prefixes=["/simple-duplicate"],
        notes="UNIFIED duplicate detection - enterprise + simple modes",
    ),
    # ========================================================================
    # AI CHAT - CONSOLIDATION TARGET
    # ========================================================================
    "unified_ai_chat": BlueprintInfo(
        name="unified_ai_chat",
        module="app.routes.unified_ai_chat_routes",
        url_prefix="/ai-chat",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=18,
        notes="PRIMARY AI chat - multi-domain chat service",
    ),
    "ai_chat": BlueprintInfo(
        name="ai_chat",
        module="app.ai_chat",
        url_prefix="/ai-chat",
        status=BlueprintStatus.DEPRECATED,
        endpoints_count=12,
        notes="Legacy AI chat routes - already consolidated",
        consolidate_into="unified_ai_chat",
    ),
    # ========================================================================
    # ENTERPRISE ARCHITECTURE - CONSOLIDATION TARGET
    # ========================================================================
    "enterprise": BlueprintInfo(
        name="enterprise",
        module="app.routes.unified_enterprise_routes",
        url_prefix="/enterprise",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=35,
        notes="PRIMARY enterprise architecture blueprint",
    ),
    "architecture": BlueprintInfo(
        name="architecture",
        module="app.routes.architecture_routes",
        url_prefix="/architecture",
        status=BlueprintStatus.DEPRECATED,
        endpoints_count=15,
        notes="Legacy architecture routes - consolidate into enterprise",
        consolidate_into="enterprise",
    ),
    "unified_low_priority": BlueprintInfo(
        name="unified_low_priority",
        module="app.routes.unified_low_priority_routes",
        url_prefix="/enterprise",
        status=BlueprintStatus.DEPRECATED,
        endpoints_count=10,
        notes="Low priority routes - merge into enterprise",
        consolidate_into="enterprise",
    ),
    "archimate_crud": BlueprintInfo(
        name="archimate_crud",
        module="app.archimate_crud",
        url_prefix="/architecture",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=20,
        notes="ArchiMate CRUD operations",
    ),
    # ========================================================================
    # CAPABILITY MANAGEMENT - CONSOLIDATION TARGET
    # ========================================================================
    "capability_map": BlueprintInfo(
        name="capability_map",
        module="app.routes.capability_map_routes",
        url_prefix="/capability-map",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=12,
        notes="Capability mapping and visualization",
    ),
    "capability_management": BlueprintInfo(
        name="capability_management",
        module="app.routes.capability_management_routes",
        url_prefix="/capability-management",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=15,
        notes="Capability CRUD and management",
    ),
    "capability_governance": BlueprintInfo(
        name="capability_governance",
        module="app.routes.capability_governance_routes",
        url_prefix="/capability-governance",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=10,
        notes="Capability governance and compliance",
    ),
    "business_capability_management": BlueprintInfo(
        name="business_capability_management",
        module="app.main.business_capability_management_routes",
        url_prefix="/business-capabilities",
        status=BlueprintStatus.DEPRECATED,
        endpoints_count=8,
        notes="Legacy business capability routes",
        consolidate_into="capability_management",
    ),
    # ========================================================================
    # DASHBOARD & TOOLS
    # ========================================================================
    "dashboard": BlueprintInfo(
        name="dashboard",
        module="app.dashboard.views",
        url_prefix="/dashboard",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=8,
        notes="Dashboard views and metrics",
    ),
    "dynamic_dashboards": BlueprintInfo(
        name="dynamic_dashboards",
        module="app.main.dynamic_dashboards",
        url_prefix="/auto-dashboard",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=10,
        notes="Auto-generated model dashboards",
    ),
    # ========================================================================
    # API v1 - VERSIONED ENDPOINTS
    # ========================================================================
    "api_v1": BlueprintInfo(
        name="api_v1",
        module="app.api.v1",
        url_prefix="/api/v1",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=25,
        notes="Versioned API with standardized responses (PRD - 003)",
    ),
    # ========================================================================
    # SPECIALIZED APIs
    # ========================================================================
    "framework_config": BlueprintInfo(
        name="framework_config",
        module="app.api.framework_config",
        url_prefix="/api/framework-config",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=12,
        notes="Framework configuration API",
    ),
    "roadmap": BlueprintInfo(
        name="roadmap",
        module="app.api.roadmap_api",
        url_prefix="/api/roadmap",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=18,
        notes="Roadmap planning and automation",
    ),
    "archimate_api": BlueprintInfo(
        name="archimate_api",
        module="app.api.archimate_routes",
        url_prefix="/api/archimate",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=15,
        notes="ArchiMate API with relationship validation",
    ),
    "viewpoint": BlueprintInfo(
        name="viewpoint",
        module="app.api.viewpoint_routes",
        url_prefix="/api/viewpoints",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=10,
        notes="ArchiMate Viewpoint Builder API",
    ),
    "intelligent_agents": BlueprintInfo(
        name="intelligent_agents",
        module="app.routes.intelligent_agents_routes",
        url_prefix="/api/agents",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=8,
        notes="AI agents for analysis and extraction",
    ),
    "code_generation": BlueprintInfo(
        name="code_generation",
        module="app.api.code_generation_routes",
        url_prefix="/code-generation",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=6,
        notes="MDD code generation API",
    ),
    "suggestions": BlueprintInfo(
        name="suggestions",
        module="app.api.suggestions_routes",
        url_prefix="/api/suggestions",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=8,
        notes="AI-powered suggestions",
    ),
    # ========================================================================
    # STRATEGIC & PLANNING
    # ========================================================================
    "strategic": BlueprintInfo(
        name="strategic",
        module="app.routes.strategic_routes",
        url_prefix="/strategic",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=12,
        notes="Strategic planning and analysis",
    ),
    "implementation_planning": BlueprintInfo(
        name="implementation_planning",
        module="app.implementation_planning",
        url_prefix="/implementation",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=10,
        notes="Implementation planning workflows",
    ),
    "consolidation_list": BlueprintInfo(
        name="consolidation_list",
        module="app.routes.consolidation_list_routes",
        url_prefix="/consolidation-list",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=8,
        notes="Application consolidation tracking",
    ),
    # ========================================================================
    # SPECIALIZED FEATURES
    # ========================================================================
    "merging": BlueprintInfo(
        name="merging",
        module="app.api.application_merging_routes",
        url_prefix="/api/merging",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=6,
        notes="Intelligent application merging",
    ),
    "capability_tagging": BlueprintInfo(
        name="capability_tagging",
        module="app.routes.capability_tagging_routes",
        url_prefix="/api/capability-tags",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=5,
        notes="Capability tagging system",
    ),
    "advanced_governance": BlueprintInfo(
        name="advanced_governance",
        module="app.routes.advanced_governance_routes",
        url_prefix="/advanced-governance",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=8,
        notes="Advanced governance automation",
    ),
    "maturity_management": BlueprintInfo(
        name="maturity_management",
        module="app.main.capability_maturity_routes",
        url_prefix="/maturity",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=6,
        notes="Capability maturity management",
    ),
    "framework_management": BlueprintInfo(
        name="framework_management",
        module="app.main.framework_management_routes",
        url_prefix="/framework-management",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=8,
        notes="Framework configuration management",
    ),
    "capability_framework": BlueprintInfo(
        name="capability_framework",
        module="app.main.capability_framework_routes",
        url_prefix="/capability-framework",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=5,
        notes="Capability framework dashboard",
    ),
    "autogen": BlueprintInfo(
        name="autogen",
        module="app.main.autogen",
        url_prefix="/autogen",
        status=BlueprintStatus.ACTIVE,
        endpoints_count=4,
        notes="AutoGen service integration",
    ),
}


# ============================================================================
# CONSOLIDATION PLAN
# ============================================================================

CONSOLIDATION_TARGETS = {
    "applications": {
        "keep": "unified_applications",
        "consolidate": ["application_mgmt", "streaming_import"],
        "priority": "HIGH",
        "estimated_effort": "2 days",
    },
    "vendors": {
        "keep": "vendors_api",
        "consolidate": ["vendors", "enhanced_vendor"],
        "priority": "HIGH",
        "estimated_effort": "2 days",
    },
    "duplicate_detection": {
        "keep": "unified_duplicate",
        "consolidate": ["duplicate_detection"],
        "priority": "COMPLETED",
        "estimated_effort": "0 days",
    },
    "ai_chat": {
        "keep": "unified_ai_chat",
        "consolidate": ["ai_chat"],
        "priority": "COMPLETED",
        "estimated_effort": "0 days",
    },
    "enterprise": {
        "keep": "enterprise",
        "consolidate": ["architecture", "unified_low_priority"],
        "priority": "MEDIUM",
        "estimated_effort": "3 days",
    },
    "capabilities": {
        "keep": "capability_management",
        "consolidate": ["business_capability_management"],
        "priority": "LOW",
        "estimated_effort": "1 day",
    },
}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def get_active_blueprints() -> List[BlueprintInfo]:
    """Get all active blueprints"""
    return [bp for bp in API_REGISTRY.values() if bp.status == BlueprintStatus.ACTIVE]


def get_deprecated_blueprints() -> List[BlueprintInfo]:
    """Get all deprecated blueprints pending consolidation"""
    return [bp for bp in API_REGISTRY.values() if bp.status == BlueprintStatus.DEPRECATED]


def get_blueprint_by_prefix(url_prefix: str) -> Optional[BlueprintInfo]:
    """Find blueprint by URL prefix"""
    for bp in API_REGISTRY.values():
        if bp.url_prefix == url_prefix:
            return bp
    return None


def get_consolidation_status() -> Dict:
    """Get consolidation progress summary"""
    total = len(API_REGISTRY)
    active = len(get_active_blueprints())
    deprecated = len(get_deprecated_blueprints())
    consolidated = len(
        [bp for bp in API_REGISTRY.values() if bp.status == BlueprintStatus.CONSOLIDATED]
    )

    return {
        "total_blueprints": total,
        "active": active,
        "deprecated": deprecated,
        "consolidated": consolidated,
        "consolidation_percentage": (consolidated / total) * 100 if total > 0 else 0,
    }


def get_health_check_endpoints() -> List[str]:
    """Get list of endpoints for health checking"""
    endpoints = []
    for bp in get_active_blueprints():
        # Add primary health check endpoint for each blueprint
        endpoints.append(f"{bp.url_prefix}/health")
    return endpoints
