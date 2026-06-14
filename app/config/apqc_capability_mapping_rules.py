"""
APQC-Capability Mapping Rules Configuration
PRD - 012: Validation rules for APQC-Capability mappings

This module provides configurable validation rules for mapping APQC processes
to business capabilities. Rules include level compatibility, confidence thresholds,
and domain-specific constraints.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LevelMappingRule:
    """Rule for mapping APQC levels to Capability levels"""

    apqc_level: int
    valid_capability_levels: List[int]
    description: str


@dataclass
class ConfidenceThreshold:
    """Confidence threshold configuration"""

    name: str
    value: float
    description: str
    action: str  # auto_approve, manual_review, reject


@dataclass
class DomainConstraint:
    """Domain-specific mapping constraint"""

    apqc_domain: str
    capability_domains: List[str]
    required: bool = False
    description: str = ""


class APQCCapabilityMappingRulesConfig:
    """
    Configuration class for APQC-Capability mapping validation rules.

    This class provides centralized configuration for all mapping validation
    rules, thresholds, and constraints used by the APQCCapabilityMappingService.
    """

    # Level Compatibility Rules
    # Defines which capability levels are valid targets for each APQC level
    LEVEL_MAPPING_RULES: Dict[int, LevelMappingRule] = {
        1: LevelMappingRule(
            apqc_level=1,
            valid_capability_levels=[1, 2],
            description="APQC Category (L1) maps to top-level capabilities",
        ),
        2: LevelMappingRule(
            apqc_level=2,
            valid_capability_levels=[2, 3],
            description="APQC Process Group (L2) maps to L2 - L3 capabilities",
        ),
        3: LevelMappingRule(
            apqc_level=3,
            valid_capability_levels=[3, 4],
            description="APQC Process (L3) maps to L3 - L4 capabilities",
        ),
        4: LevelMappingRule(
            apqc_level=4,
            valid_capability_levels=[4, 5],
            description="APQC Activity (L4) maps to leaf-level capabilities",
        ),
        5: LevelMappingRule(
            apqc_level=5,
            valid_capability_levels=[5],
            description="APQC Task (L5) maps only to L5 capabilities",
        ),
    }

    # Confidence Thresholds
    CONFIDENCE_THRESHOLDS: Dict[str, ConfidenceThreshold] = {
        "auto_approve": ConfidenceThreshold(
            name="Auto Approve",
            value=0.9,
            description="Mappings with confidence >= 0.9 are auto-approved",
            action="auto_approve",
        ),
        "manual_review": ConfidenceThreshold(
            name="Manual Review",
            value=0.8,
            description="Mappings with 0.6 <= confidence < 0.9 require manual review",
            action="manual_review",
        ),
        "required_minimum": ConfidenceThreshold(
            name="Required Minimum",
            value=0.6,
            description="Mappings below 0.6 confidence are flagged as low quality",
            action="flag_low_quality",
        ),
        "reject": ConfidenceThreshold(
            name="Reject",
            value=0.3,
            description="Mappings below 0.3 confidence should be rejected",
            action="reject",
        ),
    }

    # Confidence Score Weights
    # Defines how different factors contribute to the overall confidence score
    CONFIDENCE_WEIGHTS: Dict[str, float] = {
        "name_similarity": 0.40,  # Weight for name matching
        "description_similarity": 0.30,  # Weight for description matching
        "level_compatibility": 0.30,  # Weight for level compatibility
    }

    # Domain Mapping Constraints
    # Defines valid capability domains for each APQC domain
    DOMAIN_CONSTRAINTS: Dict[str, DomainConstraint] = {
        "finance": DomainConstraint(
            apqc_domain="Finance",
            capability_domains=["Financial Management", "Accounting", "Treasury"],
            required=False,
            description="Finance processes should map to financial capabilities",
        ),
        "hr": DomainConstraint(
            apqc_domain="Human Resources",
            capability_domains=["Human Capital Management", "Talent Management", "HR Operations"],
            required=False,
            description="HR processes should map to HR capabilities",
        ),
        "it": DomainConstraint(
            apqc_domain="Information Technology",
            capability_domains=["IT Management", "Technology Services", "Digital Operations"],
            required=False,
            description="IT processes should map to technology capabilities",
        ),
        "supply_chain": DomainConstraint(
            apqc_domain="Supply Chain",
            capability_domains=["Supply Chain Management", "Logistics", "Procurement"],
            required=False,
            description="Supply chain processes should map to operations capabilities",
        ),
        "marketing": DomainConstraint(
            apqc_domain="Marketing",
            capability_domains=["Marketing Management", "Brand Management", "Customer Engagement"],
            required=False,
            description="Marketing processes should map to marketing capabilities",
        ),
        "customer_service": DomainConstraint(
            apqc_domain="Customer Service",
            capability_domains=["Customer Experience", "Service Operations", "Support Management"],
            required=False,
            description="Customer service processes should map to CX capabilities",
        ),
    }

    # Validation Rule Severity Levels
    SEVERITY_LEVELS: Dict[str, Dict[str, Any]] = {
        "error": {
            "level": 1,
            "blocks_creation": True,
            "description": "Critical issue that prevents mapping creation",
        },
        "warning": {
            "level": 2,
            "blocks_creation": False,
            "description": "Issue that should be reviewed but does not block creation",
        },
        "info": {
            "level": 3,
            "blocks_creation": False,
            "description": "Informational message for quality improvement",
        },
    }

    # Audit Trail Configuration
    AUDIT_CONFIG: Dict[str, Any] = {
        "enabled": True,
        "retention_days": 365,
        "track_actions": ["created", "updated", "deleted", "override", "approved", "rejected"],
        "include_previous_values": True,
        "require_justification_for_override": True,
    }

    # Quality Metrics Configuration
    QUALITY_METRICS_CONFIG: Dict[str, Any] = {
        "confidence_buckets": {
            "high": {"min": 0.9, "max": 1.0},
            "medium": {"min": 0.6, "max": 0.9},
            "low": {"min": 0.0, "max": 0.6},
        },
        "target_high_confidence_ratio": 0.7,  # Target: 70% of mappings should be high confidence
        "max_low_confidence_ratio": 0.1,  # Max: 10% of mappings can be low confidence
        "review_sla_hours": 48,  # SLA for reviewing flagged mappings
    }

    @classmethod
    def get_valid_capability_levels(cls, apqc_level: int) -> List[int]:
        """Get valid capability levels for a given APQC level"""
        rule = cls.LEVEL_MAPPING_RULES.get(apqc_level)
        if rule:
            return rule.valid_capability_levels
        return [apqc_level]  # Default: same level

    @classmethod
    def is_level_compatible(cls, apqc_level: int, capability_level: int) -> bool:
        """Check if APQC level is compatible with capability level"""
        valid_levels = cls.get_valid_capability_levels(apqc_level)
        return capability_level in valid_levels

    @classmethod
    def get_confidence_action(cls, confidence_score: float) -> str:
        """Determine action based on confidence score"""
        if confidence_score >= cls.CONFIDENCE_THRESHOLDS["auto_approve"].value:
            return "auto_approve"
        elif confidence_score >= cls.CONFIDENCE_THRESHOLDS["required_minimum"].value:
            return "manual_review"
        elif confidence_score >= cls.CONFIDENCE_THRESHOLDS["reject"].value:
            return "flag_low_quality"
        else:
            return "reject"

    @classmethod
    def get_domain_constraint(cls, apqc_domain: str) -> Optional[DomainConstraint]:
        """Get domain constraint for a given APQC domain"""
        domain_key = apqc_domain.lower().replace(" ", "_")
        return cls.DOMAIN_CONSTRAINTS.get(domain_key)

    @classmethod
    def validate_domain_mapping(cls, apqc_domain: str, capability_domain: str) -> Dict[str, Any]:
        """Validate if capability domain is valid for APQC domain"""
        constraint = cls.get_domain_constraint(apqc_domain)

        if not constraint:
            return {"valid": True, "message": "No domain constraint defined"}

        is_valid = capability_domain in constraint.capability_domains

        return {
            "valid": is_valid or not constraint.required,
            "recommended": is_valid,
            "message": constraint.description if not is_valid else "Domain mapping is valid",
            "suggested_domains": constraint.capability_domains,
        }

    @classmethod
    def get_all_rules_summary(cls) -> Dict[str, Any]:
        """Get a summary of all configured rules"""
        return {
            "level_mapping_rules": {
                level: {
                    "valid_capability_levels": rule.valid_capability_levels,
                    "description": rule.description,
                }
                for level, rule in cls.LEVEL_MAPPING_RULES.items()
            },
            "confidence_thresholds": {
                name: {
                    "value": threshold.value,
                    "action": threshold.action,
                    "description": threshold.description,
                }
                for name, threshold in cls.CONFIDENCE_THRESHOLDS.items()
            },
            "confidence_weights": cls.CONFIDENCE_WEIGHTS,
            "domain_constraints_count": len(cls.DOMAIN_CONSTRAINTS),
            "audit_enabled": cls.AUDIT_CONFIG["enabled"],
            "quality_targets": {
                "high_confidence_target": cls.QUALITY_METRICS_CONFIG[
                    "target_high_confidence_ratio"
                ],
                "max_low_confidence": cls.QUALITY_METRICS_CONFIG["max_low_confidence_ratio"],
            },
        }


# Export the configuration class for use by the service
mapping_rules_config = APQCCapabilityMappingRulesConfig()
