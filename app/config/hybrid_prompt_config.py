"""
Hybrid Prompt Configuration
Settings for intelligent persona selection and prompt engineering
"""

# Complexity analysis configuration
COMPLEXITY_ANALYSIS = {
    "thresholds": {"master_persona_minimum": 5, "high_complexity": 10, "medium_complexity": 5},
    "weights": {
        "cross_domain": 3,  # Highest weight
        "technical": 2,
        "business": 2,
        "context_richness": 0.001,
        "message_length": 0.01,
    },
    "keywords": {
        "cross_domain": [
            "integrate",
            "integration",
            "governance",
            "strategy",
            "strategic",
            "transformation",
            "migration",
            "enterprise",
            "organization",
            "roadmap",
            "planning",
            "framework",
            "architecture",
            "portfolio",
        ],
        "technical": [
            "api",
            "microservices",
            "cloud",
            "security",
            "performance",
            "scalability",
            "infrastructure",
            "deployment",
            "devops",
        ],
        "business": [
            "business",
            "capability",
            "value",
            "stakeholder",
            "process",
            "operating model",
            "digital",
            "transformation",
        ],
    },
}

# Master persona configuration
MASTER_PERSONA = {
    "name": "Distinguished Enterprise Architect",
    "experience_years": 25,
    "certifications": ["TOGAF 9.2", "ArchiMate 3.2"],
    "expertise_areas": [
        "Enterprise Architecture",
        "Business Architecture",
        "Systems Architecture",
        "Solutions Architecture",
        "Application Architecture",
        "Integration Architecture",
        "Application Management",
    ],
    "traits": [
        "strategic thinking",
        "cross-domain expertise",
        "practical implementation focus",
        "change management awareness",
        "long-term sustainability perspective",
    ],
}

# Domain-specific enhancements
DOMAIN_ENHANCEMENTS = {
    "architecture": {
        "master_context_keywords": ["strategic", "governance", "roadmap", "transformation"],
        "context_weight_multiplier": 1.2,
    },
    "technology": {
        "master_context_keywords": ["integration", "platform", "scalability", "security"],
        "context_weight_multiplier": 1.1,
    },
    "business_capability": {
        "master_context_keywords": ["capability", "value", "stakeholder", "operating model"],
        "context_weight_multiplier": 1.3,
    },
    "vendor_analysis": {
        "master_context_keywords": ["strategic", "partnership", "procurement", "risk"],
        "context_weight_multiplier": 1.0,
    },
    "gap_analysis": {
        "master_context_keywords": ["transformation", "strategy", "investment", "prioritization"],
        "context_weight_multiplier": 1.4,
    },
    "database": {
        "master_context_keywords": ["governance", "quality", "architecture", "integration"],
        "context_weight_multiplier": 1.1,
    },
}

# Performance optimization settings
PERFORMANCE_CONFIG = {
    "cache_master_prompts": True,
    "cache_duration_minutes": 30,
    "max_context_length": 8000,
    "persona_selection_timeout_ms": 100,
}
