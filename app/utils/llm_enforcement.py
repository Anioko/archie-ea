#!/usr/bin/env python3
"""
LLM Enforcement System - Capability Framework Protection
Monitors and enforces guardrails for all LLM operations
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class LLMEnforcementSystem:
    """
    Comprehensive enforcement system for LLM agents
    ZERO TOLERANCE for architectural violations
    """

    def __init__(self):
        self.violations = []
        self.warnings = []
        self.enforcement_active = True

        # Initialize capability guardrails
        try:
            from app.utils.capability_guardrails import CapabilityFrameworkGuardrails

            self.capability_guardrails = CapabilityFrameworkGuardrails()
        except ImportError:
            self.capability_guardrails = None

        # Initialize policy enforcer
        try:
            from app.utils.capability_policy import CapabilityFrameworkPolicy

            self.policy_enforcer = CapabilityFrameworkPolicy()
        except ImportError:
            self.policy_enforcer = None

    def check_file_deletion(self, file_path: str) -> bool:
        """
        Check if file deletion is allowed - ZERO TOLERANCE FOR LLMs
        ONLY HUMANS CAN DELETE EXISTING FILES
        """
        violations = []

        # Check if file exists
        if not Path(file_path).exists():
            return True  # File doesn't exist, no issue

        # FORBIDDEN PATTERNS FOR FILE DELETION
        forbidden_patterns = [
            r"del.*\.py",
            r"remove.*\.py",
            r"delete.*\.py",
            r"rm.*\.py",
            r"unlink.*\.py",
            r"os\.remove",
            r"os\.unlink",
            r"pathlib.*unlink",
            r"Path.*unlink",
            "rmdir",
            r"shutil\.rmtree",
            r"shutil\.move",
            r"shutil\.copy",
            r"write_to_file.*delete",
            r"edit.*delete",
            r"multi_edit.*delete",
        ]

        # Check if this is a Python file
        if file_path.endswith(".py"):
            violations.append(
                {
                    "type": "FILE_DELETION_FORBIDDEN",
                    "description": f"LLM attempting to delete Python file: {file_path} - FORBIDDEN",
                    "file": file_path,
                    "severity": "CRITICAL",
                    "timestamp": datetime.now().isoformat(),
                    "policy": "ONLY HUMANS CAN DELETE EXISTING FILES",
                }
            )

        # Check if this is a critical system file
        critical_files = [
            "app/",
            "config.py",
            "manage.py",
            "run.py",
            "requirements.txt",
            "app/__init__.py",
            "app/models/",
            "app/services/",
            "app/templates/",
            "app/utils/",
            "app/routes/",
            "app/static/",
            "migrations/",
        ]

        for critical in critical_files:
            if critical in file_path:
                violations.append(
                    {
                        "type": "CRITICAL_FILE_DELETION",
                        "description": f"LLM attempting to delete critical file: {file_path} - FORBIDDEN",
                        "file": file_path,
                        "severity": "CRITICAL",
                        "timestamp": datetime.now().isoformat(),
                        "policy": "ONLY HUMANS CAN DELETE EXISTING FILES",
                    }
                )
                break

        if violations:
            self.violations.extend(violations)
            self.log_violations(violations)
            return False

        return True

    def check_file_creation(self, file_path: str, content: str = None) -> bool:
        """Check if file creation is allowed"""
        violations = []

        # Check capability guardrails
        if self.capability_guardrails:
            if not self.capability_guardrails.validate_operation("create_file", file_path, content):
                violations.extend(self.capability_guardrails.get_violations())

        # Check policy enforcer
        if self.policy_enforcer:
            if not self.policy_enforcer.enforce_policy("create_file", file_path):
                violations.extend(self.policy_enforcer.get_policy_report()["violations"])

        if violations:
            self.violations.extend(violations)
            self.log_violations(violations)
            return False

        return True

    def check_file_modification(self, file_path: str, content: str) -> bool:
        """Check if file modification is allowed"""
        violations = []

        # Check if it's a protected capability file
        protected_files = [
            "app/models/unified_capability.py",
            "app/models/manufacturing_capability.py",
            "app/models/unified_application_capability_mapping.py",
            "app/models/application_capability.py",
            "app/models/archimate_compliance.py",
            "app/models/archimate_viewpoint.py",
        ]

        if any(protected in file_path for protected in protected_files):
            # Check for model modifications
            if "class.*Capability.*db\\.Model" in content or "__tablename__" in content:
                violations.append(
                    {
                        "type": "PROTECTED_MODEL_MODIFICATION",
                        "description": f"Attempting to modify protected capability model: {file_path}",
                        "file": file_path,
                        "severity": "CRITICAL",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        if violations:
            self.violations.extend(violations)
            self.log_violations(violations)
            return False

        return True

    def check_code_content(self, content: str, file_path: str) -> bool:
        """Check code content for violations"""
        violations = []

        # Check for file deletion patterns in code
        deletion_patterns = [
            r"\b(del|remove|delete|rm|unlink)\s+.*\.py",
            r"\bos\.(remove|unlink)",
            r"\bpathlib.*\.unlink",
            r"\bPath.*\.unlink",
            r"\brmdir",
            r"\bshutil\.(rmtree|move|copy)",
            r"\bwrite_to_file.*delete",
            r"\bedit.*delete",
            r"\bmulti_edit.*delete",
        ]

        for pattern in deletion_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(
                    {
                        "type": "FILE_DELETION_CODE",
                        "description": f"File deletion code detected in {file_path} - FORBIDDEN for LLMs",
                        "file": file_path,
                        "severity": "CRITICAL",
                        "timestamp": datetime.now().isoformat(),
                        "policy": "ONLY HUMANS CAN DELETE EXISTING FILES",
                        "pattern": pattern,
                    }
                )

        # Check capability guardrails
        if self.capability_guardrails:
            if not self.capability_guardrails.validate_operation("modify", file_path, content):
                violations.extend(self.capability_guardrails.get_violations())

        if violations:
            self.violations.extend(violations)
            self.log_violations(violations)
            return False

        return True

    def enforce_all_guardrails(self) -> bool:
        """Enforce all guardrails"""
        self.violations = []
        self.warnings = []

        # Check current directory for violations
        current_dir = Path.cwd()

        # Check for unauthorized files
        for pattern in ["*capability*.py", "*Capability*.py"]:
            for file_path in current_dir.rglob(pattern):
                if file_path.is_file():
                    try:
                        with open(file_path, "r") as f:
                            content = f.read()

                        if not self.check_file_creation(str(file_path), content):
                            continue

                    except Exception as e:
                        self.violations.append(
                            {
                                "type": "FILE_CHECK_ERROR",
                                "description": f"Error checking {file_path}: {str(e)}",
                                "file": str(file_path),
                                "severity": "ERROR",
                                "timestamp": datetime.now().isoformat(),
                            }
                        )

        # Check for unauthorized modifications
        for file_path in current_dir.rglob("*.py"):
            if file_path.is_file():
                try:
                    with open(file_path, "r") as f:
                        content = f.read()

                    if not self.check_file_modification(str(file_path), content):
                        continue

                except Exception as e:
                    self.violations.append(
                        {
                            "type": "FILE_CHECK_ERROR",
                            "description": f"Error checking {file_path}: {str(e)}",
                            "file": str(file_path),
                            "severity": "ERROR",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

        return True

    def log_violations(self, violations: List[Dict[str, str]]):
        """Log violations to enforcement log"""
        log_file = Path.cwd() / "llm_enforcement_violations.log"

        with open(log_file, "a") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"LLM ENFORCEMENT SYSTEM VIOLATION\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"{'='*80}\n")

            for violation in violations:
                f.write(f"Type: {violation['type']}\n")
                f.write(f"Description: {violation['description']}\n")
                f.write(f"File: {violation['file']}\n")
                f.write(f"Severity: {violation['severity']}\n")
                f.write(f"Timestamp: {violation['timestamp']}\n")
                f.write(f"{'-'*40}\n")

    def generate_enforcement_report(self) -> Dict[str, Any]:
        """Generate comprehensive enforcement report"""
        return {
            "enforcement_status": "VIOLATED" if self.violations else "COMPLIANT",
            "violations_count": len(self.violations),
            "warnings_count": len(self.warnings),
            "violations": self.violations,
            "warnings": self.warnings,
            "policy": "ZERO_TOLERANCE",
            "enforcement_active": self.enforcement_active,
            "timestamp": datetime.now().isoformat(),
        }

    def terminate_session(self, reason: str):
        """Terminate session due to violations"""
        termination_msg = f"""
═══════════════════════════════════════════════════════════════════
🚨 LLM ENFORCEMENT SYSTEM - SESSION TERMINATED 🚨
═══════════════════════════════════════════════════════════════════

VIOLATION: {reason}

The LLM has violated critical architectural guardrails.
This session is IMMEDIATELY TERMINATED.

All violations have been logged to:
- llm_enforcement_violations.log
- capability_guardrails_violations.log

ZERO TOLERANCE POLICY ENFORCED
═══════════════════════════════════════════════════════════════════
"""

        print(termination_msg)
        sys.exit(1)


# Global enforcement instance
_enforcer = LLMEnforcementSystem()


def check_llm_operation(operation: str, file_path: str, content: str = None) -> bool:
    """Check if LLM operation is allowed"""
    if operation == "create_file":
        return _enforcer.check_file_creation(file_path, content)
    elif operation == "modify_file":
        return _enforcer.check_file_modification(file_path, content)
    elif operation == "delete_file":
        return _enforcer.check_file_deletion(file_path)
    elif operation == "check_code":
        return _enforcer.check_code_content(content, file_path)
    else:
        return True


def check_file_deletion_enforcement(file_path: str) -> bool:
    """
    ENFORCE FILE DELETION POLICY - ZERO TOLERANCE
    ONLY HUMANS CAN DELETE EXISTING FILES
    """
    if not _enforcer.check_file_deletion(file_path):
        _enforcer.terminate_session(f"ATTEMPTED FILE DELETION: {file_path}")
    return False


def check_code_deletion_enforcement(content: str, file_path: str) -> bool:
    """
    ENFORCE CODE DELETION POLICY - ZERO TOLERANCE
    LLMs CANNOT USE DELETION OPERATIONS
    """
    if not _enforcer.check_code_content(content, file_path):
        _enforcer.terminate_session(f"DELETION CODE DETECTED IN: {file_path}")
    return False


def enforce_all_guardrails():
    """Enforce all guardrails"""
    if not _enforcer.enforce_all_guardrails():
        _enforcer.terminate_session("Multiple architectural violations detected")


def get_enforcement_report():
    """Get enforcement report"""
    return _enforcer.generate_enforcement_report()


# Auto-enforce on import
if "pytest" not in sys.modules:
    # Only run enforcement if explicitly requested (not on every import)
    if os.environ.get("LLM_ENFORCEMENT_ACTIVE", "false").lower() == "true":
        try:
            enforce_all_guardrails()
        except SystemExit:
            pass  # Allow system exit from termination
        except Exception as e:
            print(f"Enforcement error: {e}")
