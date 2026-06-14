"""
DEPRECATED: Import from app.modules.capabilities.services instead.
-> app.modules.capabilities.services.capability_service

Capability Taxonomy Enforcement Service

Enforces business capability taxonomy rules and validation for enterprise architecture.
Provides capability level validation, domain enforcement, relationship compliance, and auto-correction.

Features:
- Rule-based capability validation
- Level and domain enforcement
- Auto-correction with audit trail
- Bulk validation with progress tracking
- Violation management and reporting
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_

from app import db

logger = logging.getLogger(__name__)


@dataclass
class ValidationViolation:
    """Individual validation violation result."""

    rule_id: Optional[int]
    rule_name: str
    violation_type: str
    severity: str
    message: str
    actual_value: str
    expected_value: str
    can_auto_correct: bool
    correction_suggestion: str


@dataclass
class ValidationResult:
    """Complete validation result for a capability."""

    is_valid: bool
    violations: List[ValidationViolation]
    corrections_applied: List[Dict[str, Any]]
    audit_entries: List[Dict[str, Any]]

    def add_violation(self, violation: ValidationViolation):
        self.violations.append(violation)
        if violation.severity in ["error", "critical"]:
            self.is_valid = False

    def add_correction(self, correction: Dict[str, Any]):
        self.corrections_applied.append(correction)

    def add_audit_entry(self, audit_entry: Dict[str, Any]):
        self.audit_entries.append(audit_entry)


class CapabilityTaxonomyService:
    """
    Comprehensive capability taxonomy enforcement service.

    Enforces business capability taxonomy rules, validates capability structure,
    and provides auto-correction capabilities with full audit trail.
    """

    def __init__(self):
        """Initialize the capability taxonomy service."""
        self._init_default_rules()
        self._init_level_definitions()
        self._init_domain_definitions()

    def _init_default_rules(self):
        """Initialize default taxonomy rules."""
        self.default_rules = {
            # Naming convention rules
            "strategic_naming": {
                "rule_name": "Strategic Capability Naming Convention",
                "rule_type": "naming_validation",
                "capability_level": "strategic",
                "pattern": r"^Strategic [A-Z][a-zA-Z\s]+ Capability$",
                "description": 'Strategic capabilities must start with "Strategic " and end with " Capability"',
                "examples": {
                    "valid": [
                        "Strategic Customer Management Capability",
                        "Strategic Digital Transformation Capability",
                    ],
                    "invalid": ["Customer Management Capability", "Strategic Customer Management"],
                },
            },
            "tactical_naming": {
                "rule_name": "Tactical Capability Naming Convention",
                "rule_type": "naming_validation",
                "capability_level": "tactical",
                "pattern": r"^[A-Z][a-zA-Z\s]+ Capability$",
                "description": 'Tactical capabilities must end with " Capability"',
                "examples": {
                    "valid": [
                        "Customer Relationship Management Capability",
                        "Supply Chain Optimization Capability",
                    ],
                    "invalid": [
                        "Customer Relationship Management",
                        "Strategic Customer Management",
                    ],
                },
            },
            "operational_naming": {
                "rule_name": "Operational Capability Naming Convention",
                "rule_type": "naming_validation",
                "capability_level": "operational",
                "pattern": r"^[a-z][a-zA-Z\s]* [a-z]+ing$",
                "description": 'Operational capabilities must end with "-ing" (e.g., "Customer Onboarding")',
                "examples": {
                    "valid": ["customer onboarding", "invoice processing", "order fulfillment"],
                    "invalid": ["Customer Onboarding Capability", "Invoice Processing Capability"],
                },
            },
            # Length validation rules
            "name_length": {
                "rule_name": "Capability Name Length Validation",
                "rule_type": "structure_validation",
                "min_length": 10,
                "max_length": 100,
                "description": "Capability names must be between 10 and 100 characters",
                "auto_correct": False,
            },
            "description_length": {
                "rule_name": "Capability Description Length Validation",
                "rule_type": "structure_validation",
                "min_length": 20,
                "max_length": 1000,
                "description": "Capability descriptions must be between 20 and 1000 characters",
                "auto_correct": False,
            },
            # Domain enforcement rules
            "business_domain_only": {
                "rule_name": "Business Domain Restriction",
                "rule_type": "domain_enforcement",
                "allowed_domains": ["business"],
                "restricted_levels": ["strategic", "tactical"],
                "description": "Strategic and tactical capabilities must be in business domain",
                "auto_correct": False,
            },
            # Level hierarchy rules
            "strategic_no_parent": {
                "rule_name": "Strategic Capability Parent Rule",
                "rule_type": "level_validation",
                "capability_level": "strategic",
                "can_have_parent": False,
                "description": "Strategic capabilities cannot have parent capabilities",
                "auto_correct": False,
            },
            "operational_must_have_parent": {
                "rule_name": "Operational Capability Parent Rule",
                "rule_type": "level_validation",
                "capability_level": "operational",
                "must_have_parent": True,
                "allowed_parent_levels": ["tactical"],
                "description": "Operational capabilities must have a tactical parent",
                "auto_correct": False,
            },
        }

    def _init_level_definitions(self):
        """Initialize capability level definitions."""
        self.level_definitions = {
            "strategic": {
                "level_number": 1,
                "naming_prefix": "Strategic ",
                "naming_suffix": " Capability",
                "allowed_domains": ["business"],
                "can_have_children": True,
                "description_required": True,
                "min_description_length": 50,
                "max_description_length": 1000,
            },
            "tactical": {
                "level_number": 2,
                "naming_prefix": "",
                "naming_suffix": " Capability",
                "allowed_domains": ["business", "technology"],
                "can_have_children": True,
                "description_required": True,
                "min_description_length": 30,
                "max_description_length": 800,
            },
            "operational": {
                "level_number": 3,
                "naming_prefix": "",
                "naming_suffix": "",
                "allowed_domains": ["business", "technology", "process"],
                "can_have_children": False,
                "description_required": True,
                "min_description_length": 20,
                "max_description_length": 500,
            },
        }

    def _init_domain_definitions(self):
        """Initialize capability domain definitions."""
        self.domain_definitions = {
            "business": {
                "domain_code": "BIZ",
                "strategic_importance": 10,
                "governance_level": "enterprise",
                "allowed_levels": ["strategic", "tactical", "operational"],
                "parent_capability_required": False,
                "max_child_capabilities": 20,
            },
            "technology": {
                "domain_code": "TECH",
                "strategic_importance": 8,
                "governance_level": "division",
                "allowed_levels": ["tactical", "operational"],
                "parent_capability_required": True,
                "max_child_capabilities": 15,
            },
            "data": {
                "domain_code": "DATA",
                "strategic_importance": 7,
                "governance_level": "department",
                "allowed_levels": ["tactical", "operational"],
                "parent_capability_required": True,
                "max_child_capabilities": 10,
            },
            "security": {
                "domain_code": "SEC",
                "strategic_importance": 9,
                "governance_level": "enterprise",
                "allowed_levels": ["strategic", "tactical", "operational"],
                "parent_capability_required": False,
                "max_child_capabilities": 12,
            },
        }

    def validate_capability(
        self, capability_data: Dict[str, Any], auto_correct: bool = False, user_id: int = None
    ) -> ValidationResult:
        """
        Validate a capability against taxonomy rules.

        Args:
            capability_data: Dictionary with capability data
            auto_correct: Whether to apply auto-corrections
            user_id: User ID for audit trail

        Returns:
            ValidationResult with violations and corrections
        """
        result = ValidationResult(
            is_valid=True, violations=[], corrections_applied=[], audit_entries=[]
        )

        # Extract capability data
        name = capability_data.get("name", "")
        description = capability_data.get("description", "")
        level = capability_data.get("level", "")
        domain = capability_data.get("domain", "")
        parent_id = capability_data.get("parent_id")

        # Validate naming conventions
        if level in self.default_rules:
            naming_rule = self.default_rules[f"{level}_naming"]
            self._validate_naming_convention(
                name, naming_rule, result, capability_data, auto_correct
            )

        # Validate length requirements
        self._validate_length_requirements(name, description, result)

        # Validate domain compliance
        if level and domain:
            self._validate_domain_compliance(level, domain, result)

        # Validate level hierarchy
        if level and parent_id:
            self._validate_level_hierarchy(level, parent_id, result)

        # Create audit entries
        if result.violations:
            audit_entry = self._create_audit_entry(
                "validation", capability_data, result.violations, user_id
            )
            result.add_audit_entry(audit_entry)

        return result

    def _validate_naming_convention(
        self,
        name: str,
        rule: Dict,
        result: ValidationResult,
        capability_data: Dict[str, Any],
        auto_correct: bool,
    ):
        """Validate naming convention for a capability."""
        import re

        pattern = rule.get("pattern", "")
        if not pattern:
            return

        # Check if name matches pattern
        if not re.match(pattern, name, re.IGNORECASE):
            violation = ValidationViolation(
                rule_id=None,
                rule_name=rule["rule_name"],
                violation_type="naming_violation",
                severity="warning",
                message=f"Naming convention violation: {rule['description']}",
                actual_value=name,
                expected_value=f"Pattern: {pattern}",
                can_auto_correct=auto_correct,
                correction_suggestion=self._generate_naming_correction(name, rule),
            )
            result.add_violation(violation)

            # Apply auto-correction if enabled
            if auto_correct and violation.can_auto_correct:
                corrected_name = self._apply_naming_correction(name, rule)
                if corrected_name != name:
                    correction = {
                        "field": "name",
                        "old_value": name,
                        "new_value": corrected_name,
                        "method": "auto_correct",
                        "rule": rule["rule_name"],
                    }
                    result.add_correction(correction)
                    capability_data["name"] = corrected_name

    def _validate_length_requirements(self, name: str, description: str, result: ValidationResult):
        """Validate length requirements for name and description."""
        # Name length validation
        name_length_rule = self.default_rules["name_length"]
        if len(name) < name_length_rule["min_length"]:
            violation = ValidationViolation(
                rule_id=None,
                rule_name=name_length_rule["rule_name"],
                violation_type="length_violation",
                severity="error",
                message=f"Name too short: {len(name)} characters (minimum: {name_length_rule['min_length']})",
                actual_value=str(len(name)),
                expected_value=f"Minimum {name_length_rule['min_length']} characters",
                can_auto_correct=False,
                correction_suggestion="Expand capability name to be more descriptive",
            )
            result.add_violation(violation)

        if len(name) > name_length_rule["max_length"]:
            violation = ValidationViolation(
                rule_id=None,
                rule_name=name_length_rule["rule_name"],
                violation_type="length_violation",
                severity="error",
                message=f"Name too long: {len(name)} characters (maximum: {name_length_rule['max_length']})",
                actual_value=str(len(name)),
                expected_value=f"Maximum {name_length_rule['max_length']} characters",
                can_auto_correct=False,
                correction_suggestion="Shorten capability name to be more concise",
            )
            result.add_violation(violation)

        # Description length validation
        if description:
            desc_length_rule = self.default_rules["description_length"]
            if len(description) < desc_length_rule["min_length"]:
                violation = ValidationViolation(
                    rule_id=None,
                    rule_name=desc_length_rule["rule_name"],
                    violation_type="length_violation",
                    severity="warning",
                    message=f"Description too short: {len(description)} characters (minimum: {desc_length_rule['min_length']})",
                    actual_value=str(len(description)),
                    expected_value=f"Minimum {desc_length_rule['min_length']} characters",
                    can_auto_correct=False,
                    correction_suggestion="Expand description to provide more context",
                )
                result.add_violation(violation)

            if len(description) > desc_length_rule["max_length"]:
                violation = ValidationViolation(
                    rule_id=None,
                    rule_name=desc_length_rule["rule_name"],
                    violation_type="length_violation",
                    severity="warning",
                    message=f"Description too long: {len(description)} characters (maximum: {desc_length_rule['max_length']})",
                    actual_value=str(len(description)),
                    expected_value=f"Maximum {desc_length_rule['max_length']} characters",
                    can_auto_correct=False,
                    correction_suggestion="Shorten description to be more concise",
                )
                result.add_violation(violation)

    def _validate_domain_compliance(self, level: str, domain: str, result: ValidationResult):
        """Validate domain compliance for capability level."""
        # Check business domain restriction for strategic/tactical capabilities
        if level in ["strategic", "tactical"]:
            business_rule = self.default_rules["business_domain_only"]
            if domain != "business":
                violation = ValidationViolation(
                    rule_id=None,
                    rule_name=business_rule["rule_name"],
                    violation_type="domain_violation",
                    severity="error",
                    message=f"Domain violation: {level} capabilities must be in business domain",
                    actual_value=domain,
                    expected_value="business",
                    can_auto_correct=True,
                    correction_suggestion="Change domain to 'business' for strategic/tactical capabilities",
                )
                result.add_violation(violation)

    def _validate_level_hierarchy(self, level: str, parent_id: int, result: ValidationResult):
        """Validate level hierarchy rules."""
        from app.models.unified_capability import UnifiedCapability

        # Get parent capability
        parent = UnifiedCapability.query.get(parent_id)
        if not parent:
            return

        parent_level = parent.level

        # Strategic capabilities cannot have parents
        if level == "strategic":
            strategic_rule = self.default_rules["strategic_no_parent"]
            violation = ValidationViolation(
                rule_id=None,
                rule_name=strategic_rule["rule_name"],
                violation_type="hierarchy_violation",
                severity="error",
                message=f"Hierarchy violation: Strategic capabilities cannot have parent capabilities",
                actual_value=f"Strategic capability with parent: {parent.name}",
                expected_value="No parent capability",
                can_auto_correct=False,
                correction_suggestion="Remove parent relationship for strategic capabilities",
            )
            result.add_violation(violation)

        # Operational capabilities must have tactical parents
        elif level == "operational":
            operational_rule = self.default_rules["operational_must_have_parent"]
            if parent_level != "tactical":
                violation = ValidationViolation(
                    rule_id=None,
                    rule_name=operational_rule["rule_name"],
                    violation_type="hierarchy_violation",
                    severity="error",
                    message=f"Hierarchy violation: Operational capabilities must have tactical parents",
                    actual_value=f"Operational capability with {parent_level} parent: {parent.name}",
                    expected_value="Tactical parent capability",
                    can_auto_correct=False,
                    correction_suggestion="Select a tactical capability as parent",
                )
                result.add_violation(violation)

    def _generate_naming_correction(self, name: str, rule: Dict) -> str:
        """Generate corrected name based on naming rule."""
        level = rule.get("capability_level", "")
        prefix = rule.get("naming_prefix", "")
        suffix = rule.get("naming_suffix", "")

        # Extract core name (remove any existing prefixes/suffixes)
        core_name = name
        if prefix and core_name.startswith(prefix):
            core_name = core_name[len(prefix) :]
        if suffix and core_name.endswith(suffix):
            core_name = core_name[: -len(suffix)]

        # Capitalize core name properly
        core_name = " ".join(word.capitalize() for word in core_name.split())

        # Apply new naming convention
        corrected_name = f"{prefix}{core_name}{suffix}"

        return corrected_name

    def _apply_naming_correction(self, name: str, rule: Dict) -> str:
        """Apply naming correction to capability name."""
        return self._generate_naming_correction(name, rule)

    def _create_audit_entry(
        self,
        action: str,
        capability_data: Dict[str, Any],
        violations: List[ValidationViolation],
        user_id: int,
    ) -> Dict[str, Any]:
        """Create audit entry for taxonomy action."""
        from app.models.application_capability import CapabilityTaxonomyAudit

        audit_entry = {
            "audit_type": "validation",
            "action": action,
            "action_description": f"Validated capability against {len(violations)} taxonomy rules",
            "capability_name": capability_data.get("name", "Unknown"),
            "before_values": {
                "name": capability_data.get("name"),
                "description": capability_data.get("description"),
                "level": capability_data.get("level"),
                "domain": capability_data.get("domain"),
                "parent_id": capability_data.get("parent_id"),
            },
            "after_values": {},
            "violations_detected": len(violations),
            "violations_corrected": 0,
            "success": len(violations) == 0,
            "user_id": user_id,
            "user_action": user_id is not None,
            "system_initiated": user_id is None,
        }

        return audit_entry

    def validate_bulk_capabilities(
        self,
        capabilities: List[Dict[str, Any]],
        auto_correct: bool = False,
        user_id: int = None,
        batch_id: str = None,
    ) -> Dict[str, Any]:
        """
        Validate multiple capabilities in bulk.

        Args:
            capabilities: List of capability data dictionaries
            auto_correct: Whether to apply auto-corrections
            user_id: User ID for audit trail
            batch_id: Batch ID for grouping operations

        Returns:
            Dictionary with bulk validation results
        """
        results = {
            "total_capabilities": len(capabilities),
            "valid_capabilities": 0,
            "invalid_capabilities": 0,
            "total_violations": 0,
            "violations_corrected": 0,
            "capability_results": [],
            "batch_id": batch_id,
        }

        for i, capability_data in enumerate(capabilities):
            try:
                validation_result = self.validate_capability(capability_data, auto_correct, user_id)

                capability_result = {
                    "index": i,
                    "capability_name": capability_data.get("name", f"Capability {i + 1}"),
                    "is_valid": validation_result.is_valid,
                    "violations_count": len(validation_result.violations),
                    "corrections_count": len(validation_result.corrections_applied),
                    "violations": [
                        {
                            "rule_name": v.rule_name,
                            "violation_type": v.violation_type,
                            "severity": v.severity,
                            "message": v.message,
                            "actual_value": v.actual_value,
                            "expected_value": v.expected_value,
                            "can_auto_correct": v.can_auto_correct,
                            "correction_suggestion": v.correction_suggestion,
                        }
                        for v in validation_result.violations
                    ],
                    "corrections": validation_result.corrections_applied,
                    "audit_entries": validation_result.audit_entries,
                }

                results["capability_results"].append(capability_result)

                if validation_result.is_valid:
                    results["valid_capabilities"] += 1
                else:
                    results["invalid_capabilities"] += 1

                results["total_violations"] += len(validation_result.violations)
                results["violations_corrected"] += len(validation_result.corrections_applied)

            except Exception as e:
                logger.error(f"Error validating capability {i}: {e}")
                capability_result = {
                    "index": i,
                    "capability_name": capability_data.get("name", f"Capability {i + 1}"),
                    "is_valid": False,
                    "violations_count": 1,
                    "corrections_count": 0,
                    "violations": [
                        {
                            "rule_name": "System Error",
                            "violation_type": "system_error",
                            "severity": "critical",
                            "message": f"Validation error: {str(e)}",
                            "actual_value": "",
                            "expected_value": "",
                            "can_auto_correct": False,
                            "correction_suggestion": "Contact system administrator",
                        }
                    ],
                    "corrections": [],
                    "audit_entries": [],
                }
                results["capability_results"].append(capability_result)
                results["invalid_capabilities"] += 1
                results["total_violations"] += 1

        # Calculate success rate
        if results["total_capabilities"] > 0:
            results["success_rate"] = results["valid_capabilities"] / results["total_capabilities"]
        else:
            results["success_rate"] = 0.0

        return results

    def get_taxonomy_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive taxonomy enforcement statistics.

        Returns:
            Dictionary with taxonomy statistics
        """
        try:
            from app.models.application_capability import (
                CapabilityDomainDefinition,
                CapabilityLevelDefinition,
                CapabilityTaxonomyAudit,
                CapabilityTaxonomyRule,
                CapabilityTaxonomyViolation,
            )

            # Rule statistics
            total_rules = CapabilityTaxonomyRule.query.filter_by(is_active=True).count()
            rules_by_type = (
                db.session.query(
                    CapabilityTaxonomyRule.rule_type,
                    func.count(CapabilityTaxonomyRule.id).label("count"),
                )
                .filter_by(is_active=True)
                .group_by(CapabilityTaxonomyRule.rule_type)
                .all()
            )

            # Violation statistics
            total_violations = CapabilityTaxonomyViolation.query.count()
            violations_by_type = (
                db.session.query(
                    CapabilityTaxonomyViolation.violation_type,
                    func.count(CapabilityTaxonomyViolation.id).label("count"),
                )
                .group_by(CapabilityTaxonomyViolation.violation_type)
                .all()
            )

            violations_by_severity = (
                db.session.query(
                    CapabilityTaxonomyViolation.severity,
                    func.count(CapabilityTaxonomyViolation.id).label("count"),
                )
                .group_by(CapabilityTaxonomyViolation.severity)
                .all()
            )

            violations_by_status = (
                db.session.query(
                    CapabilityTaxonomyViolation.status,
                    func.count(CapabilityTaxonomyViolation.id).label("count"),
                )
                .group_by(CapabilityTaxonomyViolation.status)
                .all()
            )

            # Level definitions
            level_count = CapabilityLevelDefinition.query.filter_by(is_active=True).count()

            # Domain definitions
            domain_count = CapabilityDomainDefinition.query.filter_by(is_active=True).count()

            # Audit statistics
            total_audits = CapabilityTaxonomyAudit.query.count()
            audits_by_type = (
                db.session.query(
                    CapabilityTaxonomyAudit.audit_type,
                    func.count(CapabilityTaxonomyAudit.id).label("count"),
                )
                .group_by(CapabilityTaxonomyAudit.audit_type)
                .all()
            )

            return {
                "rules": {
                    "total_active": total_rules,
                    "by_type": {rule.rule_type: rule.count for rule in rules_by_type},
                },
                "violations": {
                    "total": total_violations,
                    "by_type": {v.violation_type: v.count for v in violations_by_type},
                    "by_severity": {v.severity: v.count for v in violations_by_severity},
                    "by_status": {v.status: v.count for v in violations_by_status},
                    "resolution_rate": self._calculate_resolution_rate(),
                },
                "definitions": {"levels": level_count, "domains": domain_count},
                "audits": {
                    "total": total_audits,
                    "by_type": {audit.audit_type: audit.count for audit in audits_by_type},
                },
            }

        except Exception as e:
            logger.error(f"Error getting taxonomy statistics: {e}")
            return {"error": str(e)}

    def _calculate_resolution_rate(self) -> float:
        """Calculate violation resolution rate."""
        try:
            from app.models.application_capability import CapabilityTaxonomyViolation

            total_violations = CapabilityTaxonomyViolation.query.count()
            if total_violations == 0:
                return 100.0

            resolved_violations = CapabilityTaxonomyViolation.query.filter(
                CapabilityTaxonomyViolation.status == "corrected"
            ).count()

            return (resolved_violations / total_violations) * 100.0

        except Exception as e:
            logger.error(f"Error calculating resolution rate: {e}")
            return 0.0

    def create_taxonomy_rule(self, rule_data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """
        Create a new taxonomy rule.

        Args:
            rule_data: Dictionary with rule data
            user_id: User ID creating the rule

        Returns:
            Dictionary with creation result
        """
        try:
            from app.models.application_capability import CapabilityTaxonomyRule

            # Validate required fields
            required_fields = ["rule_name", "rule_type", "rule_category"]
            for field in required_fields:
                if not rule_data.get(field):
                    return {"success": False, "error": f"Required field missing: {field}"}

            # Check for duplicate rule name
            existing = CapabilityTaxonomyRule.query.filter_by(
                rule_name=rule_data["rule_name"]
            ).first()
            if existing:
                return {
                    "success": False,
                    "error": f'Rule with name "{rule_data["rule_name"]}" already exists',
                }

            # Create rule
            rule = CapabilityTaxonomyRule(
                rule_name=rule_data["rule_name"],
                rule_type=rule_data["rule_type"],
                rule_category=rule_data["rule_category"],
                capability_level=rule_data.get("capability_level"),
                domain=rule_data.get("domain"),
                rule_pattern=json.dumps(rule_data.get("rule_pattern", {})),
                validation_logic=rule_data.get("validation_logic"),
                is_active=rule_data.get("is_active", True),
                severity=rule_data.get("severity", "warning"),
                auto_correct=rule_data.get("auto_correct", False),
                auto_correction_logic=json.dumps(rule_data.get("auto_correction_logic", {})),
                description=rule_data.get("description"),
                examples=json.dumps(rule_data.get("examples", [])),
                created_by_id=user_id,
            )

            db.session.add(rule)
            db.session.commit()

            # Create audit entry
            audit_data = {
                "audit_type": "rule_creation",
                "action": "create_rule",
                "action_description": f"Created taxonomy rule: {rule.rule_name}",
                "rule_id": rule.id,
                "rule_name": rule.rule_name,
                "rule_type": rule.rule_type,
                "success": True,
                "user_id": user_id,
                "user_action": True,
                "system_initiated": False,
            }

            return {
                "success": True,
                "rule_id": rule.id,
                "rule": rule.to_dict(),
                "audit_entry": audit_data,
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating taxonomy rule: {e}")
            return {"success": False, "error": str(e)}

    def get_active_rules(
        self, rule_type: str = None, capability_level: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get active taxonomy rules.

        Args:
            rule_type: Optional rule type filter
            capability_level: Optional capability level filter

        Returns:
            List of active rules
        """
        try:
            from app.models.application_capability import CapabilityTaxonomyRule

            query = CapabilityTaxonomyRule.query.filter_by(is_active=True)

            if rule_type:
                query = query.filter_by(rule_type=rule_type)

            if capability_level:
                query = query.filter_by(capability_level=capability_level)

            rules = query.all()
            return [rule.to_dict() for rule in rules]

        except Exception as e:
            logger.error(f"Error getting active rules: {e}")
            return []

    def get_violations(
        self, capability_id: int = None, status: str = None, severity: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get taxonomy violations with optional filters.

        Args:
            capability_id: Optional capability ID filter
            status: Optional status filter
            severity: Optional severity filter

        Returns:
            List of violations
        """
        try:
            from app.models.application_capability import CapabilityTaxonomyViolation

            query = CapabilityTaxonomyViolation.query

            if capability_id:
                query = query.filter_by(capability_id=capability_id)

            if status:
                query = query.filter_by(status=status)

            if severity:
                query = query.filter_by(severity=severity)

            # Order by detection date (most recent first)
            query = query.order_by(CapabilityTaxonomyViolation.created_at.desc())

            violations = query.all()
            return [violation.to_dict() for violation in violations]

        except Exception as e:
            logger.error(f"Error getting violations: {e}")
            return []

    def correct_violation(
        self, violation_id: int, corrected_value: str, user_id: int
    ) -> Dict[str, Any]:
        """
        Correct a taxonomy violation.

        Args:
            violation_id: Violation ID to correct
            corrected_value: New value for the violating field
            user_id: User ID making the correction

        Returns:
            Dictionary with correction result
        """
        try:
            from app.models.application_capability import (
                CapabilityTaxonomyAudit,
                CapabilityTaxonomyViolation,
            )

            violation = CapabilityTaxonomyViolation.query.get(violation_id)
            if not violation:
                return {"success": False, "error": "Violation not found"}

            # Apply correction
            old_value = getattr(violation, violation.actual_value, "")
            violation.actual_value = old_value
            violation.expected_value = corrected_value
            violation.correction_applied = True
            violation.correction_method = "manual"
            violation.corrected_value = corrected_value
            violation.correction_date = datetime.utcnow()
            violation.corrected_by_id = user_id
            violation.status = "corrected"

            db.session.commit()

            # Update capability if needed
            if violation.capability:
                if violation.violation_type == "naming_violation":
                    violation.capability.name = corrected_value
                elif violation.violation_type == "length_violation":
                    if "name" in violation.actual_value.lower():
                        violation.capability.name = corrected_value
                    elif "description" in violation.actual_value.lower():
                        violation.capability.description = corrected_value

            # Create audit entry
            audit_data = {
                "audit_type": "correction",
                "action": "correct_violation",
                "action_description": f"Corrected violation {violation_id}: {violation.violation_type}",
                "capability_id": violation.capability_id,
                "capability_name": violation.capability.name if violation.capability else "Unknown",
                "rule_id": violation.rule_id,
                "rule_name": violation.rule_name if violation.rule else "Unknown",
                "rule_type": violation.rule_type if violation.rule else "Unknown",
                "before_values": {"value": old_value},
                "after_values": {"value": corrected_value},
                "success": True,
                "violations_corrected": 1,
                "user_id": user_id,
                "user_action": True,
                "system_initiated": False,
            }

            db.session.add(CapabilityTaxonomyAudit(**audit_data))
            db.session.commit()

            return {
                "success": True,
                "violation_id": violation_id,
                "corrected_value": corrected_value,
                "audit_entry": audit_data,
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error correcting violation {violation_id}: {e}")
            return {"success": False, "error": str(e)}
