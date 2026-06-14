"""
LLM Script Policy - Capability Framework Enforcement
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


class CapabilityFrameworkPolicy:
    """
    Enforces strict policy for LLM agents working with capability framework
    ZERO TOLERANCE for architectural violations
    """

    def __init__(self):
        self.policy_violations = []
        self.setup_policy_enforcement()

    def setup_policy_enforcement(self):
        """Setup automatic policy enforcement"""
        # Add policy enforcement to Python path
        policy_file = Path(__file__).parent / "capability_guardrails.py"
        if policy_file.exists():
            # Import guardrails to enforce on module load
            try:
                from app.utils.capability_guardrails import enforce_guardrails

                enforce_guardrails()
            except ImportError:
                pass

    def check_script_content(self, script_path: str) -> List[Dict[str, str]]:
        """Check script content for policy violations"""
        violations = []

        try:
            with open(script_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check for forbidden operations
            forbidden_operations = [
                ("CREATE TABLE", "Creating new database tables"),
                ("ALTER TABLE", "Modifying database tables"),
                ("DROP TABLE", "Dropping database tables"),
                ("class.*Capability.*Model", "Creating new capability models"),
                ("Blueprint.*capability", "Creating capability blueprints"),
                (r"db\.create_all", "Database schema operations"),
                (r"db\.drop_all", "Database schema operations"),
            ]

            for pattern, description in forbidden_operations:
                import re

                if re.search(pattern, content, re.IGNORECASE):
                    violations.append(
                        {
                            "type": "FORBIDDEN_OPERATION",
                            "pattern": pattern,
                            "description": description,
                            "file": script_path,
                            "severity": "CRITICAL",
                        }
                    )

            # Check for capability file creation
            if "capability" in script_path.lower() and script_path.endswith(".py"):
                violations.append(
                    {
                        "type": "CAPABILITY_FILE_CREATION",
                        "description": f"Creating capability-related script: {script_path}",
                        "file": script_path,
                        "severity": "CRITICAL",
                    }
                )

        except Exception as e:
            violations.append(
                {
                    "type": "POLICY_CHECK_ERROR",
                    "description": f"Error checking script {script_path}: {str(e)}",
                    "file": script_path,
                    "severity": "ERROR",
                }
            )

        return violations

    def check_directory_operations(self, directory: str) -> List[Dict[str, str]]:
        """Check directory for policy violations"""
        violations = []

        dir_path = Path(directory)
        if not dir_path.exists():
            return violations

        # Check for capability-related files
        for file_path in dir_path.rglob("*.py"):
            if "capability" in file_path.name.lower():
                violations.append(
                    {
                        "type": "CAPABILITY_FILE_IN_DIRECTORY",
                        "description": f"Capability file found in directory: {file_path}",
                        "file": str(file_path),
                        "severity": "WARNING",
                    }
                )

        return violations

    def enforce_policy(self, operation: str, target: str) -> bool:
        """Enforce policy for an operation"""
        violations = []

        if operation == "create_file":
            violations.extend(self.check_script_content(target))
        elif operation == "check_directory":
            violations.extend(self.check_directory_operations(target))

        if violations:
            self.policy_violations.extend(violations)
            return False

        return True

    def get_policy_report(self) -> Dict[str, Any]:
        """Get policy violations report"""
        return {
            "violations": self.policy_violations,
            "policy_status": "VIOLATED" if self.policy_violations else "COMPLIANT",
            "enforcement": "ZERO_TOLERANCE",
        }


# Global policy instance
_policy = CapabilityFrameworkPolicy()


def check_capability_script_policy(script_path: str) -> bool:
    """Check if script complies with capability framework policy"""
    return _policy.enforce_policy("create_file", script_path)


def check_capability_directory_policy(directory: str) -> bool:
    """Check if directory complies with capability framework policy"""
    return _policy.enforce_policy("check_directory", directory)


def enforce_capability_policy():
    """Enforce capability framework policy"""
    violations = _policy.get_policy_report()["violations"]
    if violations:
        error_msg = "🚫 CAPABILITY FRAMEWORK POLICY VIOLATIONS:\n\n"
        for violation in violations:
            error_msg += f"❌ {violation['type']}: {violation['description']}\n"
            error_msg += f"   File: {violation['file']}\n"
            error_msg += f"   Severity: {violation['severity']}\n\n"

        error_msg += "🚫 ZERO TOLERANCE POLICY\n"
        error_msg += "🚫 POLICY ENFORCEMENT ACTIVE\n"
        error_msg += "🚫 VIOLATIONS LOGGED\n"

        # Log violations to file
        log_file = Path("capability_policy_violations.log")
        with open(log_file, "a") as f:
            f.write(f"POLICY VIOLATION: {json.dumps(violations)}\n")

        raise RuntimeError(error_msg)


# Auto-enforce on import
if "pytest" not in sys.modules:
    enforce_capability_policy()
