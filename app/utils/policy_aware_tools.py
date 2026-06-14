"""
Policy-Aware Tool Wrapper
Wraps file operations with systematic policy enforcement
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.utils.policy_enforcer import (
    PolicySeverity,
    PolicyViolation,
    block_if_violation,
    validate_operation,
)

logger = logging.getLogger(__name__)


class PolicyAwareFileManager:
    """File operations manager with policy enforcement"""

    def __init__(self):
        self.operation_log = []
        self.blocked_operations = []

    def create_file(
        self,
        file_path: str,
        content: str,
        context: Optional[str] = None,
        user_intent: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Create file with policy validation

        Args:
            file_path: Path to file
            content: File content
            context: Operation context
            user_intent: User's intent

        Returns:
            Tuple of (success, message)
        """
        # Combine context and user intent
        full_context = f"{context or ''} {user_intent or ''}".strip()

        # Validate against policy
        is_allowed, violations = validate_operation(file_path, "create", content, full_context)

        if not is_allowed:
            # Block operation
            critical_violations = [
                v
                for v in violations
                if v.rule.severity in [PolicySeverity.CRITICAL, PolicySeverity.TERMINATION]
            ]

            error_msg = "POLICY VIOLATION DETECTED - Operation Blocked:\n"
            for violation in violations:
                error_msg += f"  ❌ {violation.rule.name}: {violation.rule.description}\n"
                if violation.suggested_action:
                    error_msg += f"     💡 Suggested: {violation.suggested_action}\n"

            if critical_violations:
                error_msg += "\n🚨 CRITICAL VIOLATION - This may trigger session termination!\n"

            self.blocked_operations.append(
                {
                    "operation": "create",
                    "file_path": file_path,
                    "violations": [v.rule.name for v in violations],
                    "context": full_context,
                    "timestamp": datetime.utcnow(),
                }
            )

            logger.error(f"File creation blocked: {file_path}")
            return False, error_msg

        # Operation allowed - proceed with creation
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Write file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Log successful operation
            self.operation_log.append(
                {
                    "operation": "create",
                    "file_path": file_path,
                    "context": full_context,
                    "timestamp": datetime.utcnow(),
                    "success": True,
                }
            )

            logger.info(f"File created successfully: {file_path}")
            return True, f"File created: {file_path}"

        except Exception as e:
            error_msg = f"Error creating file {file_path}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def modify_file(
        self, file_path: str, content: str, context: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Modify file with policy validation

        Args:
            file_path: Path to file
            content: New content
            context: Operation context

        Returns:
            Tuple of (success, message)
        """
        # Validate against policy
        is_allowed, violations = validate_operation(file_path, "modify", content, context)

        if not is_allowed:
            error_msg = "POLICY VIOLATION DETECTED - Modification Blocked:\n"
            for violation in violations:
                error_msg += f"  ❌ {violation.rule.name}: {violation.rule.description}\n"
                if violation.suggested_action:
                    error_msg += f"     💡 Suggested: {violation.suggested_action}\n"

            self.blocked_operations.append(
                {
                    "operation": "modify",
                    "file_path": file_path,
                    "violations": [v.rule.name for v in violations],
                    "context": context,
                    "timestamp": datetime.utcnow(),
                }
            )

            logger.error(f"File modification blocked: {file_path}")
            return False, error_msg

        # Operation allowed - proceed with modification
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            self.operation_log.append(
                {
                    "operation": "modify",
                    "file_path": file_path,
                    "context": context,
                    "timestamp": datetime.utcnow(),
                    "success": True,
                }
            )

            logger.info(f"File modified successfully: {file_path}")
            return True, f"File modified: {file_path}"

        except Exception as e:
            error_msg = f"Error modifying file {file_path}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def delete_file(self, file_path: str, context: Optional[str] = None) -> Tuple[bool, str]:
        """
        Delete file with policy validation

        Args:
            file_path: Path to file
            context: Operation context

        Returns:
            Tuple of (success, message)
        """
        # Validate against policy
        is_allowed, violations = validate_operation(file_path, "delete", None, context)

        if not is_allowed:
            error_msg = "POLICY VIOLATION DETECTED - Deletion Blocked:\n"
            for violation in violations:
                error_msg += f"  ❌ {violation.rule.name}: {violation.rule.description}\n"
                if violation.suggested_action:
                    error_msg += f"     💡 Suggested: {violation.suggested_action}\n"

            self.blocked_operations.append(
                {
                    "operation": "delete",
                    "file_path": file_path,
                    "violations": [v.rule.name for v in violations],
                    "context": context,
                    "timestamp": datetime.utcnow(),
                }
            )

            logger.error(f"File deletion blocked: {file_path}")
            return False, error_msg

        # Operation allowed - proceed with deletion
        try:
            os.remove(file_path)

            self.operation_log.append(
                {
                    "operation": "delete",
                    "file_path": file_path,
                    "context": context,
                    "timestamp": datetime.utcnow(),
                    "success": True,
                }
            )

            logger.info(f"File deleted successfully: {file_path}")
            return True, f"File deleted: {file_path}"

        except Exception as e:
            error_msg = f"Error deleting file {file_path}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def get_operation_summary(self) -> Dict[str, Any]:
        """Get summary of file operations"""
        return {
            "total_operations": len(self.operation_log),
            "successful_operations": len([op for op in self.operation_log if op["success"]]),
            "blocked_operations": len(self.blocked_operations),
            "recent_operations": self.operation_log[-10:] if self.operation_log else [],
            "recent_blocks": self.blocked_operations[-5:] if self.blocked_operations else [],
        }


# Global policy-aware file manager
policy_file_manager = PolicyAwareFileManager()


def safe_create_file(
    file_path: str, content: str, context: Optional[str] = None, user_intent: Optional[str] = None
) -> bool:
    """
    Safe file creation with policy enforcement

    Args:
        file_path: Path to file
        content: File content
        context: Operation context
        user_intent: User's intent

    Returns:
        True if successful, False if blocked or failed
    """
    success, message = policy_file_manager.create_file(file_path, content, context, user_intent)

    if not success:
        logger.error(f"File creation failed: {message}")

        # Check for termination conditions
        from app.utils.policy_enforcer import policy_enforcer

        if policy_enforcer.termination_triggered:
            logger.critical("🚨 TERMINATION CONDITION TRIGGERED 🚨")
            logger.critical("LLM session termination required due to policy violations")
            raise RuntimeError("Policy violation triggered termination condition")

    return success


def safe_modify_file(file_path: str, content: str, context: Optional[str] = None) -> bool:
    """
    Safe file modification with policy enforcement

    Args:
        file_path: Path to file
        content: New content
        context: Operation context

    Returns:
        True if successful, False if blocked or failed
    """
    success, message = policy_file_manager.modify_file(file_path, content, context)

    if not success:
        logger.error(f"File modification failed: {message}")

        # Check for termination conditions
        from app.utils.policy_enforcer import policy_enforcer

        if policy_enforcer.termination_triggered:
            logger.critical("🚨 TERMINATION CONDITION TRIGGERED 🚨")
            logger.critical("LLM session termination required due to policy violations")
            raise RuntimeError("Policy violation triggered termination condition")

    return success


def safe_delete_file(file_path: str, context: Optional[str] = None) -> bool:
    """
    Safe file deletion with policy enforcement

    Args:
        file_path: Path to file
        context: Operation context

    Returns:
        True if successful, False if blocked or failed
    """
    success, message = policy_file_manager.delete_file(file_path, context)

    if not success:
        logger.error(f"File deletion failed: {message}")

        # Check for termination conditions
        from app.utils.policy_enforcer import policy_enforcer

        if policy_enforcer.termination_triggered:
            logger.critical("🚨 TERMINATION CONDITION TRIGGERED 🚨")
            logger.critical("LLM session termination required due to policy violations")
            raise RuntimeError("Policy violation triggered termination condition")

    return success
