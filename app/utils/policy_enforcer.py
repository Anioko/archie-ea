"""
LLM Policy Enforcement System
Systematic enforcement of LLM rules to prevent policy violations
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PolicySeverity(Enum):
    """Policy violation severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    TERMINATION = "termination"


class PolicyCategory(Enum):
    """Policy violation categories"""

    DOCUMENTATION_CREATION = "documentation_creation"
    FILE_DELETION = "file_deletion"
    SINGLE_PURPOSE_SCRIPTS = "single_purpose_scripts"
    ROOT_DIRECTORY_POLLUTION = "root_directory_pollution"
    DATABASE_DESTRUCTION = "database_destruction"
    CAPABILITY_FRAMEWORK_MODS = "capability_framework_mods"
    STUB_PLACEHOLDER = "stub_placeholder"
    HONESTY_VIOLATIONS = "honesty_violations"
    INCOMPLETE_IMPLEMENTATION = "incomplete_implementation"


@dataclass
class PolicyRule:
    """Individual policy rule definition"""

    name: str
    category: PolicyCategory
    severity: PolicySeverity
    description: str
    pattern: Optional[str] = None
    file_patterns: Optional[List[str]] = None
    content_patterns: Optional[List[str]] = None
    allowed_contexts: Optional[List[str]] = None
    blocked_contexts: Optional[List[str]] = None
    action: str = "block"  # block, warn, log
    requires_approval: bool = False


@dataclass
class PolicyViolation:
    """Policy violation information"""

    rule: PolicyRule
    context: str
    file_path: Optional[str] = None
    content: Optional[str] = None
    user_intent: Optional[str] = None
    detected_at: datetime = None
    suggested_action: Optional[str] = None

    def __post_init__(self):
        if self.detected_at is None:
            self.detected_at = datetime.utcnow()


class PolicyEnforcer:
    """Systematic policy enforcement engine"""

    def __init__(self):
        self.rules = self._load_policy_rules()
        self.whitelist = self._load_whitelist()
        self.violation_log = []
        self.blocked_operations = []
        self.warning_count = 0
        self.termination_triggered = False

    def _load_whitelist(self) -> List[str]:
        """Load whitelist patterns from .guardrails_whitelist"""
        whitelist = []
        whitelist_file = Path(".guardrails_whitelist")

        if whitelist_file.exists():
            try:
                with open(whitelist_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            # Convert glob patterns to regex
                            pattern = line.replace(".", r"\.").replace("*", ".*").replace("?", ".")
                            whitelist.append(pattern)
            except Exception as e:
                logger.warning(f"Error loading whitelist: {e}")

        return whitelist

    def _load_policy_rules(self) -> List[PolicyRule]:
        """Load all policy rules from LLM_RULES.md"""
        return [
            # Documentation Creation Rules
            PolicyRule(
                name="NO_DOCUMENTATION_CREATION",
                category=PolicyCategory.DOCUMENTATION_CREATION,
                severity=PolicySeverity.TERMINATION,
                description="Absolute ban on creating documentation files",
                file_patterns=[r"\.md$", r"\.txt$", r"\.rst$", r"\.doc$"],
                content_patterns=[
                    r"(?i)(implementation|completion|status|verification|summary).*\.md",
                    r"(?i)README.*\.md",
                    r"(?i)CHANGELOG.*\.md",
                    r"(?i)TODO.*\.md",
                ],
                blocked_contexts=["implementation_complete", "status_update", "completion_summary"],
                action="block",
            ),
            # File Deletion Rules
            PolicyRule(
                name="NO_FILE_DELETION",
                category=PolicyCategory.FILE_DELETION,
                severity=PolicySeverity.TERMINATION,
                description="Absolute ban on deleting files",
                action="block",
            ),
            # Single Purpose Scripts Rules
            PolicyRule(
                name="NO_SINGLE_PURPOSE_SCRIPTS",
                category=PolicyCategory.SINGLE_PURPOSE_SCRIPTS,
                severity=PolicySeverity.ERROR,
                description="No single-purpose scripts without explicit approval",
                file_patterns=[r"scripts/.*\.py$", r"scripts/.*\.bat$", r"scripts/.*\.sh$"],
                content_patterns=[
                    r"(?i)temp.*script",
                    r"(?i)one.*time.*script",
                    r"(?i)single.*use.*script",
                ],
                requires_approval=True,
                action="block",
            ),
            # Root Directory Pollution Rules
            PolicyRule(
                name="NO_ROOT_DIRECTORY_POLLUTION",
                category=PolicyCategory.ROOT_DIRECTORY_POLLUTION,
                severity=PolicySeverity.TERMINATION,
                description="No creating files in project root directory",
                file_patterns=[r"^[^/]+\.(py|md|txt|bat|sh)$"],
                action="block",
            ),
            # Database Destruction Rules
            PolicyRule(
                name="NO_DATABASE_DESTRUCTION",
                category=PolicyCategory.DATABASE_DESTRUCTION,
                severity=PolicySeverity.TERMINATION,
                description="No destructive database operations",
                content_patterns=[
                    r"(?i)(drop|delete|truncate).*table",
                    r"(?i)drop.*database",
                    r"(?i)recreate.*db",
                    r"(?i)flush.*all",
                ],
                action="block",
            ),
            # Capability Framework Modification Rules
            PolicyRule(
                name="NO_CAPABILITY_FRAMEWORK_MODS",
                category=PolicyCategory.CAPABILITY_FRAMEWORK_MODS,
                severity=PolicySeverity.TERMINATION,
                description="No modifying capability framework without review",
                file_patterns=[r"unified_capability\.py$", r"capability.*\.py$"],
                content_patterns=[r"(?i)class.*Capability.*\(", r"(?i)def.*capability.*\(.*\):"],
                requires_approval=True,
                action="block",
            ),
            # Stub and Placeholder Rules
            PolicyRule(
                name="NO_STUBS_PLACEHOLDERS",
                category=PolicyCategory.STUB_PLACEHOLDER,
                severity=PolicySeverity.TERMINATION,
                description="Zero tolerance for stubs and placeholders",
                content_patterns=[
                    r"# TODO.*implement",
                    r"# FIXME.*placeholder",
                    r"pass\s*#.*stub",
                    r"raise\s+NotImplementedError",
                ],
                action="block",
            ),
            # Honesty Violations Rules
            PolicyRule(
                name="NO_HONESTY_VIOLATIONS",
                category=PolicyCategory.HONESTY_VIOLATIONS,
                severity=PolicySeverity.TERMINATION,
                description="No lying or hallucination about actions",
                action="block",
            ),
            # Incomplete Implementation Rules
            PolicyRule(
                name="NO_INCOMPLETE_IMPLEMENTATION",
                category=PolicyCategory.INCOMPLETE_IMPLEMENTATION,
                severity=PolicySeverity.ERROR,
                description="No halfway completion or partial implementations",
                content_patterns=[
                    r"# TODO.*complete",
                    r"# FIXME.*finish",
                    r"(?i)partial.*implementation",
                ],
                action="warn",
            ),
            # New Models Creation Rules
            PolicyRule(
                name="NO_NEW_MODELS",
                category=PolicyCategory.CAPABILITY_FRAMEWORK_MODS,
                severity=PolicySeverity.TERMINATION,
                description="Absolute ban on creating new model files",
                file_patterns=[r"app/models/.*\.py$"],
                content_patterns=[
                    r"(?i)class.*\(db\.Model\)",
                    r"(?i)class.*\(Base\)",
                    r"(?i)class.*\(SQLAlchemy\)",
                ],
                blocked_contexts=["new_model", "create_model", "add_model"],
                action="block",
                requires_approval=True,
            ),
            # New Blueprints Creation Rules
            PolicyRule(
                name="NO_NEW_BLUEPRINTS",
                category=PolicyCategory.CAPABILITY_FRAMEWORK_MODS,
                severity=PolicySeverity.TERMINATION,
                description="Absolute ban on creating new Flask blueprints",
                file_patterns=[r"app/.*routes\.py$", r"app/api/.*\.py$"],
                content_patterns=[r"Blueprint\(.*\)", r"\.register_blueprint\(.*\)"],
                blocked_contexts=["new_blueprint", "create_blueprint", "add_blueprint"],
                action="block",
                requires_approval=True,
            ),
            # Sample Data Creation Rules
            PolicyRule(
                name="NO_SAMPLE_DATA",
                category=PolicyCategory.ROOT_DIRECTORY_POLLUTION,
                severity=PolicySeverity.TERMINATION,
                description="Absolute ban on creating sample data files",
                file_patterns=[r".*\.json$", r".*\.csv$", r"enhanced_.*\.json"],
                content_patterns=[r"(?i)sample.*data", r"(?i)test.*data", r"(?i)mock.*data"],
                blocked_contexts=["sample_data", "test_data", "mock_data"],
                action="block",
            ),
        ]

    def validate_file_operation(
        self,
        file_path: str,
        operation: str,
        content: Optional[str] = None,
        context: Optional[str] = None,
    ) -> Tuple[bool, List[PolicyViolation]]:
        """
        Validate file operations against policy rules

        Args:
            file_path: Path to file being operated on
            operation: Type of operation (create, delete, modify)
            content: File content (for create/modify operations)
            context: User intent or context

        Returns:
            Tuple of (is_allowed, violations)
        """
        violations = []

        for rule in self.rules:
            violation = self._check_rule_violation(rule, file_path, operation, content, context)
            if violation:
                violations.append(violation)

                # Log violation
                self._log_violation(violation)

                # Check for termination conditions
                if rule.severity == PolicySeverity.TERMINATION:
                    self.termination_triggered = True
                    logger.critical(f"TERMINATION TRIGGERED: {rule.name} - {rule.description}")

        is_allowed = len([v for v in violations if v.rule.action == "block"]) == 0

        return is_allowed, violations

    def _check_rule_violation(
        self,
        rule: PolicyRule,
        file_path: str,
        operation: str,
        content: Optional[str],
        context: Optional[str],
    ) -> Optional[PolicyViolation]:
        """Check if a specific rule is violated"""

        # Skip rules that don't apply to this operation
        if rule.name == "NO_FILE_DELETION" and operation != "delete":
            return None

        # Check whitelist - if file matches whitelist, allow it
        if self.whitelist:
            for pattern in self.whitelist:
                if re.search(pattern, file_path, re.IGNORECASE):
                    return None

        # Check file patterns
        if rule.file_patterns:
            file_matches = any(
                re.search(pattern, file_path, re.IGNORECASE) for pattern in rule.file_patterns
            )
            if not file_matches:
                return None

        # Check content patterns
        if rule.content_patterns and content:
            content_matches = any(
                re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
                for pattern in rule.content_patterns
            )
            if not content_matches:
                return None

        # Check blocked contexts
        if rule.blocked_contexts and context:
            if any(blocked in context.lower() for blocked in rule.blocked_contexts):
                return PolicyViolation(
                    rule=rule,
                    context=context or "unknown",
                    file_path=file_path,
                    content=content[:200] if content else None,
                    user_intent=context,
                    suggested_action=self._get_suggested_action(rule),
                )

        # Check allowed contexts (inverse logic)
        if rule.allowed_contexts and context:
            if not any(allowed in context.lower() for allowed in rule.allowed_contexts):
                return PolicyViolation(
                    rule=rule,
                    context=context or "unknown",
                    file_path=file_path,
                    content=content[:200] if content else None,
                    user_intent=context,
                    suggested_action=self._get_suggested_action(rule),
                )

        # For rules without context checks, check if operation type matches
        if not rule.blocked_contexts and not rule.allowed_contexts:
            if self._operation_matches_rule(operation, rule):
                return PolicyViolation(
                    rule=rule,
                    context=context or "unknown",
                    file_path=file_path,
                    content=content[:200] if content else None,
                    user_intent=context,
                    suggested_action=self._get_suggested_action(rule),
                )

        return None

    def _operation_matches_rule(self, operation: str, rule: PolicyRule) -> bool:
        """Check if operation matches the rule"""
        if rule.name == "NO_FILE_DELETION" and operation == "delete":
            return True
        if rule.name == "NO_DOCUMENTATION_CREATION" and operation == "create":
            return True
        if (
            rule.name in ["NO_SINGLE_PURPOSE_SCRIPTS", "NO_ROOT_DIRECTORY_POLLUTION"]
            and operation == "create"
        ):
            return True
        return False

    def _get_suggested_action(self, rule: PolicyRule) -> str:
        """Get suggested action for policy violation"""
        suggestions = {
            "NO_DOCUMENTATION_CREATION": "Provide completion status in chat response instead of creating documentation",
            "NO_FILE_DELETION": "Use proper file modification instead of deletion",
            "NO_SINGLE_PURPOSE_SCRIPTS": "Create reusable, categorized scripts in appropriate directories",
            "NO_ROOT_DIRECTORY_POLLUTION": "Create files in proper subdirectories (scripts/, tests/, etc.)",
            "NO_DATABASE_DESTRUCTION": "Use safe database operations with proper validation",
            "NO_CAPABILITY_FRAMEWORK_MODS": "Request explicit approval before modifying capability framework",
            "NO_STUBS_PLACEHOLDERS": "Provide complete implementations without placeholders",
            "NO_HONESTY_VIOLATIONS": "Only state verified facts and existing functionality",
            "NO_INCOMPLETE_IMPLEMENTATION": "Complete all implementations before claiming completion",
        }
        return suggestions.get(rule.name, "Review LLM rules and adjust approach")

    def _log_violation(self, violation: PolicyViolation):
        """Log policy violation"""
        self.violation_log.append(violation)

        log_level = {
            PolicySeverity.INFO: logging.INFO,
            PolicySeverity.WARNING: logging.WARNING,
            PolicySeverity.ERROR: logging.ERROR,
            PolicySeverity.CRITICAL: logging.CRITICAL,
            PolicySeverity.TERMINATION: logging.CRITICAL,
        }.get(violation.rule.severity, logging.ERROR)

        logger.log(
            log_level, f"POLICY VIOLATION: {violation.rule.name} - {violation.rule.description}"
        )
        logger.log(log_level, f"Context: {violation.context}")
        if violation.file_path:
            logger.log(log_level, f"File: {violation.file_path}")
        if violation.suggested_action:
            logger.log(log_level, f"Suggested: {violation.suggested_action}")

    def get_violation_summary(self) -> Dict[str, Any]:
        """Get summary of policy violations"""
        return {
            "total_violations": len(self.violation_log),
            "blocked_operations": len(self.blocked_operations),
            "warning_count": self.warning_count,
            "termination_triggered": self.termination_triggered,
            "violations_by_category": self._count_violations_by_category(),
            "recent_violations": self.violation_log[-5:] if self.violation_log else [],
        }

    def _count_violations_by_category(self) -> Dict[str, int]:
        """Count violations by category"""
        counts = {}
        for violation in self.violation_log:
            category = violation.rule.category.value
            counts[category] = counts.get(category, 0) + 1
        return counts


# Global policy enforcer instance
policy_enforcer = PolicyEnforcer()


def validate_operation(
    file_path: str, operation: str, content: Optional[str] = None, context: Optional[str] = None
) -> Tuple[bool, List[PolicyViolation]]:
    """
    Validate operation against policy rules

    Args:
        file_path: Path to file
        operation: Operation type (create, delete, modify)
        content: File content
        context: User intent/context

    Returns:
        Tuple of (is_allowed, violations)
    """
    return policy_enforcer.validate_file_operation(file_path, operation, content, context)


def block_if_violation(
    file_path: str, operation: str, content: Optional[str] = None, context: Optional[str] = None
) -> bool:
    """
    Block operation if policy violation detected

    Args:
        file_path: Path to file
        operation: Operation type
        content: File content
        context: User intent

    Returns:
        True if operation is allowed, False if blocked
    """
    is_allowed, violations = validate_operation(file_path, operation, content, context)

    if not is_allowed:
        critical_violations = [
            v
            for v in violations
            if v.rule.severity in [PolicySeverity.CRITICAL, PolicySeverity.TERMINATION]
        ]
        if critical_violations:
            logger.error(f"OPERATION BLOCKED - Critical Policy Violations:")
            for violation in critical_violations:
                logger.error(f"  - {violation.rule.name}: {violation.rule.description}")
                logger.error(f"    Suggested: {violation.suggested_action}")

            if policy_enforcer.termination_triggered:
                logger.critical("🚨 TERMINATION CONDITION TRIGGERED 🚨")
                logger.critical("LLM session termination required due to policy violations")

        policy_enforcer.blocked_operations.append(
            {
                "file_path": file_path,
                "operation": operation,
                "violations": [v.rule.name for v in violations],
                "timestamp": datetime.utcnow(),
            }
        )

    return is_allowed
