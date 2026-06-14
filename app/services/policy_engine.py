"""
Policy Engine Service

Rules engine (OPA-like) for ARB gates and governance policy enforcement.
Implements policy-as-code approach for architecture governance decisions.

Features:
- Policy definition and validation
- Rule evaluation engine
- Policy versioning and audit trail
- Integration with ARB workflow
- Compliance checking and reporting
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PolicyResult(Enum):
    """Policy evaluation results."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    ERROR = "error"


class PolicyScope(Enum):
    """Policy application scopes."""

    ARCHITECTURE = "architecture"
    CAPABILITY = "capability"
    APPLICATION = "application"
    INFRASTRUCTURE = "infrastructure"
    SECURITY = "security"
    COMPLIANCE = "compliance"


@dataclass
class PolicyRule:
    """Individual policy rule definition."""

    rule_id: str
    name: str
    description: str
    scope: PolicyScope
    condition: str  # Python expression or JSON logic
    action: str  # What to do when condition is met
    severity: PolicyResult
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PolicyEvaluation:
    """Result of policy evaluation."""

    policy_id: str
    rule_id: str
    target_id: str
    target_type: str
    result: PolicyResult
    message: str
    details: Dict[str, Any]
    evaluated_at: datetime = field(default_factory=datetime.utcnow)
    evaluator: str = ""


class PolicyEngine:
    """
    Rules engine for governance policy enforcement.

    Implements policy-as-code with:
    - Declarative policy definitions
    - Runtime evaluation
    - Audit trail and reporting
    - Integration with ARB workflow
    """

    def __init__(self):
        self.policies: Dict[str, List[PolicyRule]] = {}
        self._load_default_policies()

    def _load_default_policies(self):
        """Load default governance policies."""
        # Architecture consistency policies
        self.policies["architecture_consistency"] = [
            PolicyRule(
                rule_id="arch_001",
                name="TOGAF ADM Phase Alignment",
                description="Ensure architecture changes align with appropriate ADM phase",
                scope=PolicyScope.ARCHITECTURE,
                condition="target.get('adm_phase') in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']",
                action="validate_adm_alignment",
                severity=PolicyResult.FAIL,
                metadata={"togaf_version": "9.2", "mandatory": True},
            ),
            PolicyRule(
                rule_id="arch_002",
                name="ArchiMate Viewpoint Compliance",
                description="Validate use of appropriate ArchiMate viewpoints",
                scope=PolicyScope.ARCHITECTURE,
                condition="len(target.get('viewpoints', [])) > 0",
                action="validate_viewpoints",
                severity=PolicyResult.WARN,
                metadata={"archimate_version": "3.2"},
            ),
            PolicyRule(
                rule_id="arch_003",
                name="Architecture Debt Threshold",
                description="Flag architectures with high technical debt",
                scope=PolicyScope.ARCHITECTURE,
                condition="target.get('technical_debt_score', 0) > 7.0",
                action="flag_technical_debt",
                severity=PolicyResult.WARN,
                metadata={"threshold": 7.0},
            ),
        ]

        # Capability governance policies
        self.policies["capability_governance"] = [
            PolicyRule(
                rule_id="cap_001",
                name="Capability Maturity Assessment",
                description="Require maturity assessment for capability changes",
                scope=PolicyScope.CAPABILITY,
                condition="target.get('maturity_assessment_required', True)",
                action="assess_maturity",
                severity=PolicyResult.FAIL,
                metadata={"assessment_levels": ["1", "2", "3", "4", "5"]},
            ),
            PolicyRule(
                rule_id="cap_002",
                name="Business Value Justification",
                description="Require business value justification for new capabilities",
                scope=PolicyScope.CAPABILITY,
                condition="target.get('business_value_score', 0) >= 3",
                action="validate_business_value",
                severity=PolicyResult.FAIL,
                metadata={"minimum_score": 3},
            ),
        ]

        # Security policies
        self.policies["security_governance"] = [
            PolicyRule(
                rule_id="sec_001",
                name="Security Architecture Review",
                description="Require security review for infrastructure changes",
                scope=PolicyScope.SECURITY,
                condition="target.get('security_impact') in ['high', 'critical']",
                action="require_security_review",
                severity=PolicyResult.FAIL,
                metadata={"review_required": True},
            ),
            PolicyRule(
                rule_id="sec_002",
                name="Data Classification Compliance",
                description="Ensure proper data classification and handling",
                scope=PolicyScope.SECURITY,
                condition="target.get('data_classification') in ['public', 'internal', 'confidential', 'restricted']",
                action="validate_data_handling",
                severity=PolicyResult.FAIL,
                metadata={"classifications": ["public", "internal", "confidential", "restricted"]},
            ),
        ]

    def evaluate_policies(
        self, target: Dict[str, Any], scope: PolicyScope, context: Optional[Dict[str, Any]] = None
    ) -> List[PolicyEvaluation]:
        """
        Evaluate all applicable policies for a target.

        Args:
            target: The object being evaluated
            scope: Policy scope to evaluate
            context: Additional evaluation context

        Returns:
            List of policy evaluation results
        """
        results = []
        target_id = target.get("id", "unknown")
        target_type = target.get("type", "unknown")

        # Get policies for this scope
        scope_policies = self.policies.get(f"{scope.value}_governance", [])

        for policy in scope_policies:
            if not policy.enabled:
                continue

            try:
                evaluation = self._evaluate_rule(policy, target, context or {})
                evaluation.target_id = target_id
                evaluation.target_type = target_type
                results.append(evaluation)
            except Exception as e:
                logger.error(f"Policy evaluation failed for rule {policy.rule_id}: {e}")
                results.append(
                    PolicyEvaluation(
                        policy_id=f"{scope.value}_governance",
                        rule_id=policy.rule_id,
                        target_id=target_id,
                        target_type=target_type,
                        result=PolicyResult.ERROR,
                        message=f"Evaluation error: {str(e)}",
                        details={"error": str(e)},
                    )
                )

        return results

    def _evaluate_rule(
        self, rule: PolicyRule, target: Dict[str, Any], context: Dict[str, Any]
    ) -> PolicyEvaluation:
        """Evaluate a single policy rule."""
        # Simple condition evaluation (in production, use a proper expression evaluator)
        try:
            # For demo purposes, implement basic condition checking
            condition_met = self._check_condition(rule.condition, target, context)

            if condition_met:
                result = rule.severity
                message = f"Policy {rule.name}: {rule.action}"
            else:
                result = PolicyResult.PASS
                message = f"Policy {rule.name}: Condition not met"

            return PolicyEvaluation(
                policy_id=f"{rule.scope.value}_governance",
                rule_id=rule.rule_id,
                target_id="",  # Will be set by caller
                target_type="",
                result=result,
                message=message,
                details={
                    "rule": rule.name,
                    "condition": rule.condition,
                    "action": rule.action,
                    "target_data": target,
                },
            )

        except Exception as e:
            return PolicyEvaluation(
                policy_id=f"{rule.scope.value}_governance",
                rule_id=rule.rule_id,
                target_id="",
                target_type="",
                result=PolicyResult.ERROR,
                message=f"Rule evaluation failed: {str(e)}",
                details={"error": str(e), "rule": rule.name},
            )

    def _check_condition(
        self, condition: str, target: Dict[str, Any], context: Dict[str, Any]
    ) -> bool:
        """Simple condition checker (replace with proper expression engine in production)."""
        # Basic condition examples
        if "target.get('adm_phase') in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']" in condition:
            return target.get("adm_phase") in ["A", "B", "C", "D", "E", "F", "G", "H"]

        if "len(target.get('viewpoints', [])) > 0" in condition:
            return len(target.get("viewpoints", [])) > 0

        if "target.get('technical_debt_score', 0) > 7.0" in condition:
            return target.get("technical_debt_score", 0) > 7.0

        if "target.get('maturity_assessment_required', True)" in condition:
            return target.get("maturity_assessment_required", True)

        if "target.get('business_value_score', 0) >= 3" in condition:
            return target.get("business_value_score", 0) >= 3

        if "target.get('security_impact') in ['high', 'critical']" in condition:
            return target.get("security_impact") in ["high", "critical"]

        if (
            "target.get('data_classification') in ['public', 'internal', 'confidential', 'restricted']"
            in condition
        ):
            return target.get("data_classification") in [
                "public",
                "internal",
                "confidential",
                "restricted",
            ]

        # Default to True for unknown conditions (in production, raise error)
        return True

    def get_policy_summary(self, evaluations: List[PolicyEvaluation]) -> Dict[str, Any]:
        """Generate policy evaluation summary."""
        summary = {
            "total_evaluations": len(evaluations),
            "passed": 0,
            "failed": 0,
            "warnings": 0,
            "errors": 0,
            "overall_result": PolicyResult.PASS,
            "critical_failures": [],
            "policy_results": [],
        }

        for eval in evaluations:
            if eval.result == PolicyResult.PASS:
                summary["passed"] += 1
            elif eval.result == PolicyResult.FAIL:
                summary["failed"] += 1
                if eval.result == PolicyResult.FAIL:
                    summary["critical_failures"].append(eval.message)
            elif eval.result == PolicyResult.WARN:
                summary["warnings"] += 1
            elif eval.result == PolicyResult.ERROR:
                summary["errors"] += 1

            summary["policy_results"].append(
                {"rule_id": eval.rule_id, "result": eval.result.value, "message": eval.message}
            )

        # Determine overall result
        if summary["failed"] > 0 or summary["errors"] > 0:
            summary["overall_result"] = PolicyResult.FAIL
        elif summary["warnings"] > 0:
            summary["overall_result"] = PolicyResult.WARN

        return summary

    def add_custom_policy(self, policy_set: str, rule: PolicyRule):
        """Add a custom policy rule."""
        if policy_set not in self.policies:
            self.policies[policy_set] = []
        self.policies[policy_set].append(rule)
        logger.info(f"Added custom policy rule: {rule.rule_id}")

    def disable_policy(self, policy_set: str, rule_id: str):
        """Disable a policy rule."""
        if policy_set in self.policies:
            for rule in self.policies[policy_set]:
                if rule.rule_id == rule_id:
                    rule.enabled = False
                    logger.info(f"Disabled policy rule: {rule_id}")
                    break
