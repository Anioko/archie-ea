"""
Enhanced Tool Wrapper with Runtime Policy Validation
Wraps all file operations with automatic policy checking
"""

import logging
import os
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.utils.policy_aware_tools import safe_create_file, safe_delete_file, safe_modify_file
from app.utils.policy_enforcer import (
    PolicySeverity,
    PolicyViolation,
    block_if_violation,
    validate_operation,
)

logger = logging.getLogger(__name__)


class PolicyViolationError(Exception):
    """Exception raised when policy violation is detected"""

    def __init__(
        self, violations: List[PolicyViolation], message: str = "Policy violation detected"
    ):
        self.violations = violations
        self.message = message
        super().__init__(message)

        # Check for termination conditions
        critical_violations = [
            v
            for v in violations
            if v.rule.severity in [PolicySeverity.CRITICAL, PolicySeverity.TERMINATION]
        ]
        if critical_violations:
            self.is_termination = True
            logger.critical("🚨 POLICY VIOLATION TRIGGERED TERMINATION 🚨")
            for violation in critical_violations:
                logger.critical(f"  - {violation.rule.name}: {violation.rule.description}")
        else:
            self.is_termination = False


def policy_validated_operation(operation_type: str = "create"):
    """
    Decorator for policy validation of file operations

    Args:
        operation_type: Type of operation (create, modify, delete)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract file_path from function arguments
            file_path = kwargs.get("file_path") or (args[0] if args else None)

            if not file_path:
                logger.error("No file path provided for policy validation")
                raise ValueError("File path is required for policy validation")

            # Extract content and context
            content = kwargs.get("content") or (args[1] if len(args) > 1 else None)
            context = kwargs.get("context") or kwargs.get("user_intent")

            # Validate against policy
            is_allowed, violations = validate_operation(file_path, operation_type, content, context)

            if not is_allowed:
                # Block operation and raise exception
                error_msg = (
                    f"Policy violation detected for {operation_type} operation on {file_path}"
                )
                raise PolicyViolationError(violations, error_msg)

            # Operation allowed - proceed
            try:
                result = func(*args, **kwargs)
                logger.info(f"Policy-validated {operation_type} operation completed: {file_path}")
                return result
            except Exception as e:
                logger.error(f"Error in policy-validated operation: {str(e)}")
                raise

        return wrapper

    return decorator


class PolicyAwareToolWrapper:
    """Wrapper for tools with automatic policy enforcement"""

    def __init__(self):
        self.operation_history = []
        self.violation_history = []

    @policy_validated_operation("create")
    def create_file(
        self, file_path: str, content: str, context: Optional[str] = None, **kwargs
    ) -> bool:
        """Create file with policy validation"""
        return safe_create_file(file_path, content, context, kwargs.get("user_intent"))

    @policy_validated_operation("modify")
    def modify_file(
        self, file_path: str, content: str, context: Optional[str] = None, **kwargs
    ) -> bool:
        """Modify file with policy validation"""
        return safe_modify_file(file_path, content, context)

    @policy_validated_operation("delete")
    def delete_file(self, file_path: str, context: Optional[str] = None, **kwargs) -> bool:
        """Delete file with policy validation"""
        return safe_delete_file(file_path, context)

    def validate_before_operation(
        self,
        file_path: str,
        operation: str,
        content: Optional[str] = None,
        context: Optional[str] = None,
    ) -> Tuple[bool, List[PolicyViolation]]:
        """
        Pre-operation validation check

        Args:
            file_path: Path to file
            operation: Operation type
            content: File content
            context: Operation context

        Returns:
            Tuple of (is_allowed, violations)
        """
        return validate_operation(file_path, operation, content, context)

    def get_policy_status(self) -> Dict[str, Any]:
        """Get current policy enforcement status"""
        from app.utils.policy_enforcer import policy_enforcer

        return {
            "total_operations": len(self.operation_history),
            "total_violations": len(self.violation_history),
            "termination_triggered": policy_enforcer.termination_triggered,
            "recent_operations": self.operation_history[-10:] if self.operation_history else [],
            "recent_violations": self.violation_history[-5:] if self.violation_history else [],
            "policy_summary": policy_enforcer.get_violation_summary(),
        }


# Global policy-aware tool wrapper
policy_tool_wrapper = PolicyAwareToolWrapper()


def enforce_policy_on_tool_call(tool_name: str, **kwargs):
    """
    Enforce policy on any tool call

    Args:
        tool_name: Name of the tool being called
        **kwargs: Tool arguments

    Returns:
        Tool result or raises PolicyViolationError
    """
    # Map tool names to operations
    tool_operation_map = {
        "write_to_file": "create",
        "edit": "modify",
        "multi_edit": "modify",
        "delete_file": "delete",
    }

    operation = tool_operation_map.get(tool_name)
    if not operation:
        # No policy enforcement for this tool
        logger.info(f"No policy enforcement for tool: {tool_name}")
        return None

    # Extract relevant arguments
    file_path = kwargs.get("file_path") or kwargs.get("TargetFile")
    content = kwargs.get("content") or kwargs.get("CodeContent")
    context = kwargs.get("context") or kwargs.get("explanation")

    if not file_path:
        logger.warning(f"No file path found for policy enforcement on tool: {tool_name}")
        return None

    # Validate operation
    is_allowed, violations = validate_operation(file_path, operation, content, context)

    if not is_allowed:
        error_msg = f"Policy violation detected for tool {tool_name} on {file_path}"
        raise PolicyViolationError(violations, error_msg)

    # Log successful validation
    policy_tool_wrapper.operation_history.append(
        {
            "tool_name": tool_name,
            "file_path": file_path,
            "operation": operation,
            "context": context,
            "timestamp": datetime.utcnow(),
            "validated": True,
        }
    )

    logger.info(f"Policy validation passed for tool: {tool_name} on {file_path}")
    return True


# Enhanced tool wrappers with policy enforcement
def policy_enforced_write_to_file(
    file_path: str, content: str, context: Optional[str] = None, **kwargs
) -> bool:
    """Policy-enforced file writing"""
    try:
        enforce_policy_on_tool_call(
            "write_to_file", file_path=file_path, content=content, context=context
        )
        return policy_tool_wrapper.create_file(file_path, content, context, **kwargs)
    except PolicyViolationError as e:
        policy_tool_wrapper.violation_history.append(
            {
                "tool_name": "write_to_file",
                "file_path": file_path,
                "violations": [v.rule.name for v in e.violations],
                "timestamp": datetime.utcnow(),
                "termination_triggered": e.is_termination,
            }
        )
        raise


def policy_enforced_edit(
    file_path: str, old_string: str, new_string: str, context: Optional[str] = None, **kwargs
) -> bool:
    """Policy-enforced file editing"""
    try:
        # For edit operations, we need to check the new content
        enforce_policy_on_tool_call(
            "edit", file_path=file_path, content=new_string, context=context
        )

        # Read existing content
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                existing_content = f.read()
        except FileNotFoundError:
            existing_content = ""

        # Replace content
        modified_content = existing_content.replace(old_string, new_string)

        return policy_tool_wrapper.modify_file(file_path, modified_content, context)
    except PolicyViolationError as e:
        policy_tool_wrapper.violation_history.append(
            {
                "tool_name": "edit",
                "file_path": file_path,
                "violations": [v.rule.name for v in e.violations],
                "timestamp": datetime.utcnow(),
                "termination_triggered": e.is_termination,
            }
        )
        raise


def policy_enforced_delete(file_path: str, context: Optional[str] = None, **kwargs) -> bool:
    """Policy-enforced file deletion"""
    try:
        enforce_policy_on_tool_call("delete_file", file_path=file_path, context=context)
        return policy_tool_wrapper.delete_file(file_path, context)
    except PolicyViolationError as e:
        policy_tool_wrapper.violation_history.append(
            {
                "tool_name": "delete_file",
                "file_path": file_path,
                "violations": [v.rule.name for v in e.violations],
                "timestamp": datetime.utcnow(),
                "termination_triggered": e.is_termination,
            }
        )
        raise


# Policy monitoring and reporting
def get_policy_compliance_report() -> Dict[str, Any]:
    """Get comprehensive policy compliance report"""
    from app.utils.policy_enforcer import policy_enforcer

    return {
        "enforcement_status": {
            "total_operations_checked": len(policy_tool_wrapper.operation_history),
            "total_violations_detected": len(policy_tool_wrapper.violation_history),
            "termination_triggered": policy_enforcer.termination_triggered,
            "compliance_rate": (
                len(policy_tool_wrapper.operation_history)
                - len(policy_tool_wrapper.violation_history)
            )
            / max(len(policy_tool_wrapper.operation_history), 1)
            * 100,
        },
        "violation_breakdown": policy_enforcer.get_violation_summary(),
        "recent_activity": {
            "operations": policy_tool_wrapper.operation_history[-10:]
            if policy_tool_wrapper.operation_history
            else [],
            "violations": policy_tool_wrapper.violation_history[-5:]
            if policy_tool_wrapper.violation_history
            else [],
        },
        "policy_health": {
            "critical_violations": len(
                [
                    v
                    for v in policy_tool_wrapper.violation_history
                    if any(
                        viol.rule.severity in [PolicySeverity.CRITICAL, PolicySeverity.TERMINATION]
                        for violation in v["violations"]
                    )
                ]
            ),
            "warnings": len(
                [
                    v
                    for v in policy_tool_wrapper.violation_history
                    if any(
                        viol.rule.rule.severity == PolicySeverity.WARNING
                        for violation in v["violations"]
                    )
                ]
            ),
            "status": "HEALTHY"
            if not policy_enforcer.termination_triggered
            else "TERMINATION_REQUIRED",
        },
    }


def check_policy_health() -> bool:
    """Check if policy enforcement system is healthy"""
    from app.utils.policy_enforcer import policy_enforcer

    return not policy_enforcer.termination_triggered
