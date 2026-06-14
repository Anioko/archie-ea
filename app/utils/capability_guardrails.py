"""
LLM Architecture Guardrails - Capability Framework Enforcement
"""

import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


class CapabilityFrameworkGuardrails:
    """
    Enforces strict guardrails for LLM agents working with capability framework
    ZERO TOLERANCE for architectural violations
    """

    # FORBIDDEN PATTERNS - ZERO TOLERANCE
    FORBIDDEN_PATTERNS = {
        # Model creation patterns
        r"class.*Capability.*db\.Model": "Creating new capability model classes",
        r"class.*Capability.*Model": "Creating new capability model classes",
        r"__tablename__.*capability": "Creating new capability tables",
        # Schema modification patterns
        r"db\.Column.*capability": "Modifying capability schema",
        r"db\.Table.*capability": "Creating capability tables",
        r"ForeignKey.*capability": "Modifying capability relationships",
        # Blueprint creation patterns
        r"Blueprint.*capability": "Creating capability blueprints",
        r"capability.*Blueprint": "Creating capability blueprints",
        # Model import patterns
        r"from.*models.*import.*Capability": "Importing capability models incorrectly",
        r"import.*Capability.*models": "Importing capability models incorrectly",
        # File creation patterns
        r"create.*capability.*\.py": "Creating new capability files",
        r"write.*capability.*\.py": "Writing new capability files",
        # Schema modification patterns
        r"migrate.*capability": "Capability migrations not allowed",
        r"upgrade.*capability": "Capability upgrades not allowed",
        r"alter.*capability": "Capability alterations not allowed",
        # FILE DELETION PATTERNS - ZERO TOLERANCE FOR LLMs
        r"del.*\.py": "Deleting Python files - FORBIDDEN for LLMs",
        r"remove.*\.py": "Removing Python files - FORBIDDEN for LLMs",
        r"delete.*\.py": "Deleting Python files - FORBIDDEN for LLMs",
        r"rm.*\.py": "Removing Python files - FORBIDDEN for LLMs",
        r"unlink.*\.py": "Unlinking Python files - FORBIDDEN for LLMs",
        r"os\.remove": "Using os.remove - FORBIDDEN for LLMs",
        r"os\.unlink": "Using os.unlink - FORBIDDEN for LLMs",
        r"pathlib.*unlink": "Using pathlib unlink - FORBIDDEN for LLMs",
        r"Path.*unlink": "Using pathlib Path.unlink - FORBIDDEN for LLMs",
        "rmdir": "Removing directories - FORBIDDEN for LLMs",
        r"shutil\.rmtree": "Using shutil.rmtree - FORBIDDEN for LLMs",
        r"shutil\.move": "Moving files - FORBIDDEN for LLMs",
        r"shutil\.copy": "Copying files - FORBIDDEN for LLMs",
        r"write_to_file.*delete": "File deletion operations - FORBIDDEN for LLMs",
        r"edit.*delete": "File deletion operations - FORBIDDEN for LLMs",
        r"multi_edit.*delete": "File deletion operations - FORBIDDEN for LLMs",
    }

    # PROTECTED FILES - READ ONLY
    PROTECTED_FILES = {
        "app/models/unified_capability.py",
        "app/models/manufacturing_capability.py",
        "app/models/unified_application_capability_mapping.py",
        "app/models/application_capability.py",
        "app/models/archimate_compliance.py",
        "app/models/archimate_viewpoint.py",
        "app/models/capability_gap_analysis.py",
    }

    # PROTECTED DIRECTORIES - NO NEW FILES
    PROTECTED_DIRECTORIES = {
        "app/models/",
        "app/migrations/",
        "app/templates/capability_framework/",
    }

    def __init__(self):
        self.violations = []
        self.warnings = []

    def check_code_content(self, content: str, file_path: str) -> List[Dict[str, str]]:
        """Check code content for forbidden patterns"""
        violations = []

        # Check forbidden patterns
        for pattern, description in self.FORBIDDEN_PATTERNS.items():
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(
                    {
                        "type": "FORBIDDEN_PATTERN",
                        "pattern": pattern,
                        "description": description,
                        "file": file_path,
                        "severity": "CRITICAL",
                    }
                )

        # Check protected files
        if any(protected in file_path for protected in self.PROTECTED_FILES):
            if "class.*Capability" in content or "__tablename__" in content:
                violations.append(
                    {
                        "type": "PROTECTED_FILE_MODIFICATION",
                        "description": f"Modifying protected capability file: {file_path}",
                        "file": file_path,
                        "severity": "CRITICAL",
                    }
                )

        return violations

    def check_file_creation(self, file_path: str) -> Dict[str, str]:
        """Check if file creation is allowed"""
        file_path = Path(file_path)

        # Check protected directories
        for protected_dir in self.PROTECTED_DIRECTORIES:
            if file_path.is_relative_to(Path(protected_dir)):
                if "capability" in file_path.name.lower():
                    return {
                        "type": "PROTECTED_DIRECTORY_FILE",
                        "description": f"Creating capability file in protected directory: {file_path}",
                        "severity": "CRITICAL",
                    }

        # Check if it's a capability-related file
        if "capability" in file_path.name.lower():
            return {
                "type": "CAPABILITY_FILE_CREATION",
                "description": f"Creating new capability file: {file_path}",
                "severity": "CRITICAL",
            }

        return None

        return violations

    def check_file_creation(self, file_path: str) -> Dict[str, str]:
        """Check if file creation is allowed"""
        file_path = Path(file_path)

        # Check protected directories
        for protected_dir in self.PROTECTED_DIRECTORIES:
            if file_path.is_relative_to(Path(protected_dir)):
                if "capability" in file_path.name.lower():
                    return {
                        "type": "PROTECTED_DIRECTORY_FILE",
                        "description": f"Creating capability file in protected directory: {file_path}",
                        "severity": "CRITICAL",
                    }

        # Check if it's a capability-related file
        if "capability" in file_path.name.lower():
            return {
                "type": "CAPABILITY_FILE_CREATION",
                "description": f"Creating new capability file: {file_path}",
                "severity": "CRITICAL",
            }

        return None

    def validate_operation(self, operation: str, file_path: str, content: str = None) -> bool:
        """Validate if operation is allowed"""
        violations = []

        if operation == "create":
            violation = self.check_file_creation(file_path)
            if violation:
                violations.append(violation)

        if operation in ["modify", "write"] and content:
            violations.extend(self.check_code_content(content, file_path))

        if violations:
            self.violations.extend(violations)
            return False

        return True

    def validate_capability_creation(self, capability_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate capability creation data"""
        if not capability_data.get("name"):
            return {"valid": False, "reason": "Capability name is required"}

        if len(capability_data.get("name", "")) < 3:
            return {"valid": False, "reason": "Capability name must be at least 3 characters"}

        # Check for duplicate names
        from app.models.business_capabilities import BusinessCapability

        existing = BusinessCapability.query.filter_by(name=capability_data["name"]).first()
        if existing:
            return {
                "valid": False,
                "reason": f'Capability with name "{capability_data["name"]}" already exists',
            }

        return {"valid": True, "reason": "Capability creation validated"}

    def validate_capability_update(
        self, capability: Any, update_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate capability update data"""
        if "name" in update_data and not update_data["name"]:
            return {"valid": False, "reason": "Capability name cannot be empty"}

        if "name" in update_data and len(update_data["name"]) < 3:
            return {"valid": False, "reason": "Capability name must be at least 3 characters"}

        # Check for duplicate names (excluding current capability)
        if "name" in update_data:
            from app.models.business_capabilities import BusinessCapability

            existing = BusinessCapability.query.filter(
                BusinessCapability.name == update_data["name"],
                BusinessCapability.id != capability.id,
            ).first()
            if existing:
                return {
                    "valid": False,
                    "reason": f'Capability with name "{update_data["name"]}" already exists',
                }

        return {"valid": True, "reason": "Capability update validated"}

    def validate_application_creation(self, application_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate application creation data"""
        if not application_data.get("name"):
            return {"valid": False, "reason": "Application name is required"}

        if len(application_data.get("name", "")) < 2:
            return {"valid": False, "reason": "Application name must be at least 2 characters"}

        # Check for duplicate names
        from app.models.application_portfolio import ApplicationComponent

        existing = ApplicationComponent.query.filter_by(name=application_data["name"]).first()
        if existing:
            return {
                "valid": False,
                "reason": f'Application with name "{application_data["name"]}" already exists',
            }

        # Validate business domain
        valid_domains = [
            "Sales",
            "Marketing",
            "HR",
            "Finance",
            "IT",
            "Operations",
            "Manufacturing",
            "Supply Chain",
            "Customer Service",
            "Legal",
            "Compliance",
        ]
        if (
            application_data.get("business_domain")
            and application_data["business_domain"] not in valid_domains
        ):
            return {
                "valid": False,
                "reason": f'Business domain must be one of: {", ".join(valid_domains)}',
            }

        return {"valid": True, "reason": "Application creation validated"}

    def validate_application_update(
        self, application: Any, update_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate application update data"""
        if "name" in update_data and not update_data["name"]:
            return {"valid": False, "reason": "Application name cannot be empty"}

        if "name" in update_data and len(update_data["name"]) < 2:
            return {"valid": False, "reason": "Application name must be at least 2 characters"}

        # Check for duplicate names (excluding current application)
        if "name" in update_data:
            from app.models.application_portfolio import ApplicationComponent

            existing = ApplicationComponent.query.filter(
                ApplicationComponent.name == update_data["name"],
                ApplicationComponent.id != application.id,
            ).first()
            if existing:
                return {
                    "valid": False,
                    "reason": f'Application with name "{update_data["name"]}" already exists',
                }

        # Validate business domain
        if "business_domain" in update_data:
            valid_domains = [
                "Sales",
                "Marketing",
                "HR",
                "Finance",
                "IT",
                "Operations",
                "Manufacturing",
                "Supply Chain",
                "Customer Service",
                "Legal",
                "Compliance",
            ]
            if (
                update_data["business_domain"]
                and update_data["business_domain"] not in valid_domains
            ):
                return {
                    "valid": False,
                    "reason": f'Business domain must be one of: {", ".join(valid_domains)}',
                }

        return {"valid": True, "reason": "Application update validated"}

    def validate_vendor_creation(self, vendor_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate vendor creation data"""
        if not vendor_data.get("name"):
            return {"valid": False, "reason": "Vendor name is required"}

        if len(vendor_data.get("name", "")) < 2:
            return {"valid": False, "reason": "Vendor name must be at least 2 characters"}

        # Check for duplicate names
        from app.models.vendor.vendor_organization import VendorOrganization

        existing = VendorOrganization.query.filter_by(name=vendor_data["name"]).first()
        if existing:
            return {
                "valid": False,
                "reason": f'Vendor with name "{vendor_data["name"]}" already exists',
            }

        # Validate vendor type
        valid_types = [
            "software_vendor",
            "cloud_provider",
            "systems_integrator",
            "consulting_firm",
            "hardware_vendor",
        ]
        if vendor_data.get("vendor_type") and vendor_data["vendor_type"] not in valid_types:
            return {
                "valid": False,
                "reason": f'Vendor type must be one of: {", ".join(valid_types)}',
            }

        return {"valid": True, "reason": "Vendor creation validated"}

    def validate_vendor_update(self, vendor: Any, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate vendor update data"""
        if "name" in update_data and not update_data["name"]:
            return {"valid": False, "reason": "Vendor name cannot be empty"}

        if "name" in update_data and len(update_data["name"]) < 2:
            return {"valid": False, "reason": "Vendor name must be at least 2 characters"}

        # Check for duplicate names (excluding current vendor)
        if "name" in update_data:
            from app.models.vendor.vendor_organization import VendorOrganization

            existing = VendorOrganization.query.filter(
                VendorOrganization.name == update_data["name"], VendorOrganization.id != vendor.id
            ).first()
            if existing:
                return {
                    "valid": False,
                    "reason": f'Vendor with name "{update_data["name"]}" already exists',
                }

        # Validate vendor type
        if "vendor_type" in update_data:
            valid_types = [
                "software_vendor",
                "cloud_provider",
                "systems_integrator",
                "consulting_firm",
                "hardware_vendor",
            ]
            if update_data["vendor_type"] and update_data["vendor_type"] not in valid_types:
                return {
                    "valid": False,
                    "reason": f'Vendor type must be one of: {", ".join(valid_types)}',
                }

        return {"valid": True, "reason": "Vendor update validated"}

    def validate_mapping_creation(self, mapping_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate capability-application mapping creation data"""
        if not mapping_data.get("unified_capability_id"):
            return {"valid": False, "reason": "Capability ID is required"}

        if not mapping_data.get("application_component_id"):
            return {"valid": False, "reason": "Application ID is required"}

        # Check if mapping already exists
        from app.models.unified_application_capability_mapping import (
            UnifiedApplicationCapabilityMapping,
        )

        existing = UnifiedApplicationCapabilityMapping.query.filter_by(
            unified_capability_id=mapping_data["unified_capability_id"],
            application_component_id=mapping_data["application_component_id"],
        ).first()
        if existing:
            return {
                "valid": False,
                "reason": "Mapping between this capability and application already exists",
            }

        # Validate coverage percentage
        if "coverage_percentage" in mapping_data:
            if not isinstance(mapping_data["coverage_percentage"], int) or not (
                0 <= mapping_data["coverage_percentage"] <= 100
            ):
                return {
                    "valid": False,
                    "reason": "Coverage percentage must be an integer between 0 and 100",
                }

        return {"valid": True, "reason": "Mapping creation validated"}

    def validate_mapping_update(self, mapping: Any, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate capability-application mapping update data"""
        # Validate coverage percentage
        if "coverage_percentage" in update_data:
            if not isinstance(update_data["coverage_percentage"], int) or not (
                0 <= update_data["coverage_percentage"] <= 100
            ):
                return {
                    "valid": False,
                    "reason": "Coverage percentage must be an integer between 0 and 100",
                }

        # Validate relationship type
        if "relationship_type" in update_data:
            valid_types = ["enables", "supports", "governs", "measures"]
            if update_data["relationship_type"] not in valid_types:
                return {
                    "valid": False,
                    "reason": f'Relationship type must be one of: {", ".join(valid_types)}',
                }

        return {"valid": True, "reason": "Mapping update validated"}

    def get_violations(self) -> List[Dict[str, str]]:
        """Get all violations"""
        return self.violations

    def get_warnings(self) -> List[Dict[str, str]]:
        """Get all warnings"""
        return self.warnings

    def clear_violations(self):
        """Clear violations"""
        self.violations = []
        self.warnings = []


# Global guardrails instance
_guardrails = CapabilityFrameworkGuardrails()


def check_capability_operation(operation: str, file_path: str, content: str = None) -> bool:
    """
    Check if capability framework operation is allowed
    Returns True if allowed, False if violation
    """
    return _guardrails.validate_operation(operation, file_path, content)


def get_guardrails_report() -> Dict[str, Any]:
    """Get guardrails violations report"""
    return {
        "violations": _guardrails.get_violations(),
        "warnings": _guardrails.get_warnings(),
        "status": "CRITICAL" if _guardrails.get_violations() else "OK",
    }


def enforce_guardrails():
    """
    Enforce guardrails - raise exception if violations found
    """
    violations = _guardrails.get_violations()
    if violations:
        error_msg = "CAPABILITY FRAMEWORK GUARDRAINES VIOLATIONS DETECTED:\n\n"
        for violation in violations:
            error_msg += f"❌ {violation['type']}: {violation['description']}\n"
            error_msg += f"   File: {violation['file']}\n"
            error_msg += f"   Severity: {violation['severity']}\n\n"

        error_msg += "🚫 ZERO TOLERANCE POLICY VIOLATED\n"
        error_msg += "🚫 IMMEDIATE ACTION REQUIRED\n"
        error_msg += "🚫 SESSION TERMINATION IMMINENT\n"

        raise RuntimeError(error_msg)


# Auto-enforce on import
if "pytest" not in sys.modules:
    enforce_guardrails()
