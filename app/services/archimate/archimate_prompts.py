"""
DEPRECATED: Import from app.modules.architecture.services instead.
-> app.modules.architecture.services.archimate_prompts
Backward-compat re-export. Canonical: app/modules/architecture/services/archimate_prompts.py
"""
from app.modules.architecture.services.archimate_prompts import (  # noqa: F401
    build_archimate_prompt,
    get_few_shot_examples,
    detect_scenario,
    get_scenario_prompt,
    ARCHIMATE_SYSTEM_PROMPT,
    GENERATE_ARCHIMATE_FROM_REQUIREMENTS,
    VALIDATE_ARCHIMATE_MODEL,
    DETECT_ARCHIMATE_PATTERNS,
    RECOMMEND_ARCHIMATE_VIEWPOINTS,
    ANALYZE_CHANGE_IMPACT,
    GENERATE_ARCHIMATE_DOCUMENTATION,
    SUGGEST_CAPABILITY_IMPROVEMENTS,
    DIGITAL_TRANSFORMATION_PROMPT,
    CLOUD_MIGRATION_PROMPT,
    APPLICATION_MODERNIZATION_PROMPT,
    ENTERPRISE_INTEGRATION_PROMPT,
    DATA_ANALYTICS_PLATFORM_PROMPT,
    SCENARIO_PATTERNS,
)
