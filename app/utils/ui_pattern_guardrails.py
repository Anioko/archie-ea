"""
UI Pattern Guardrails - Unified Modal Enforcement
ZERO TOLERANCE for UI pattern violations
"""

import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


class UIPatternGuardrails:
    """
    Enforces strict guardrails for LLM agents working with UI patterns
    ZERO TOLERANCE for unified modal violations
    """

    # UNIFIED MAPPING MODAL - MANDATORY USAGE
    UNIFIED_MAPPING_MODAL = {
        "template_path": "app/templates/components/unified_mapping_modal.html",
        "required_include": "{% include 'components/unified_mapping_modal.html' %}",
        "forbidden_patterns": [
            r"<div.*mapping.*modal.*class.*hidden",
            r'id="[^"]*mapping[^"]*modal"',
            r"openMappingModal.*function",
            r"closeMappingModal.*function",
            r"mapping-modal.*class.*fixed.*inset - 0",
            r"Map Applications to.*span.*id.*modal",
            r"onclick.*openMappingModal",
            r"onclick.*closeMappingModal",
            r"function.*openMappingModal",
            r"function.*closeMappingModal",
            r"window\.openMappingModal",
            r"window\.closeMappingModal",
        ],
        "metadata_fields": [
            "coverage_percentage",
            "relationship_type",
            "business_criticality",
            "implementation_status",
            "notes",
            "tags",
            "priority",
            "business_owner",
            "technical_owner",
        ],
        "required_ui_elements": [
            "search",
            "filter",
            "bulk-select",
            "pagination",
            "metadata-editing",
            "save-mappings",
        ],
    }

    # FORBIDDEN UI PATTERNS - ZERO TOLERANCE
    FORBIDDEN_UI_PATTERNS = {
        # Custom mapping modals
        r'<div.*id=".*mapping.*modal"': "Creating custom mapping modals - MUST use unified_mapping_modal.html",
        r'class=".*mapping.*modal"': "Custom modal classes - MUST use unified modal",
        r"Map Applications to:": "Custom modal headers - MUST use unified modal",
        # Custom modal functions
        r"function.*openMappingModal": "Custom modal functions - MUST use unified modal functions",
        r"function.*closeMappingModal": "Custom modal functions - MUST use unified modal functions",
        r"window\.openMappingModal": "Custom window functions - MUST use unified modal",
        r"window\.closeMappingModal": "Custom window functions - MUST use unified modal",
        # Custom modal styling
        r"mapping-modal.*fixed.*inset - 0": "Custom modal styling - MUST use unified modal",
        r"bg-gray - 600.*bg-opacity - 50.*mapping": "Custom modal backdrop - MUST use unified modal",
        # Custom modal triggers
        r"onclick.*openMappingModal": "Custom modal triggers - MUST use unified modal functions",
        r"onclick.*closeMappingModal": "Custom modal triggers - MUST use unified modal functions",
        r"data-bs-toggle.*mapping": "Bootstrap modal patterns - MUST use unified modal",
        r"data-bs-target.*mapping": "Bootstrap modal patterns - MUST use unified modal",
    }

    def __init__(self):
        self.violations = []
        self.warnings = []

    def check_ui_pattern_compliance(self, content: str, file_path: str) -> List[Dict[str, str]]:
        """Check UI pattern compliance for template files"""
        violations = []

        # Only check HTML template files
        if not file_path.endswith(".html"):
            return violations

        # Check for forbidden UI patterns
        for pattern, description in self.FORBIDDEN_UI_PATTERNS.items():
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(
                    {
                        "type": "FORBIDDEN_UI_PATTERN",
                        "pattern": pattern,
                        "description": description,
                        "file": file_path,
                        "severity": "CRITICAL",
                    }
                )

        # Check unified mapping modal compliance
        violations.extend(self._check_unified_mapping_modal_compliance(content, file_path))

        return violations

    def _check_unified_mapping_modal_compliance(
        self, content: str, file_path: str
    ) -> List[Dict[str, str]]:
        """Check for unified mapping modal compliance violations"""
        violations = []

        # Check for mapping modal functionality
        has_mapping_modal = "mapping" in content.lower() and "modal" in content.lower()

        if not has_mapping_modal:
            return violations

        # Check if required include is present
        if self.UNIFIED_MAPPING_MODAL["required_include"] not in content:
            violations.append(
                {
                    "type": "MISSING_UNIFIED_MODAL_INCLUDE",
                    "pattern": self.UNIFIED_MAPPING_MODAL["required_include"],
                    "description": "Mapping modal detected but unified_mapping_modal.html include not found",
                    "file": file_path,
                    "severity": "CRITICAL",
                }
            )

        # Check for forbidden patterns specifically for mapping modals
        for pattern in self.UNIFIED_MAPPING_MODAL["forbidden_patterns"]:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(
                    {
                        "type": "UNIFIED_MODAL_VIOLATION",
                        "pattern": pattern,
                        "description": f"Custom mapping modal pattern detected - MUST use unified_mapping_modal.html",
                        "file": file_path,
                        "severity": "CRITICAL",
                    }
                )

        # Check for missing metadata fields
        content_lower = content.lower()
        for field in self.UNIFIED_MAPPING_MODAL["metadata_fields"]:
            if field not in content_lower:
                violations.append(
                    {
                        "type": "MISSING_METADATA_FIELD",
                        "pattern": field,
                        "description": f"Missing required metadata field: {field}",
                        "file": file_path,
                        "severity": "CRITICAL",
                    }
                )

        # Check for missing UI elements
        for element in self.UNIFIED_MAPPING_MODAL["required_ui_elements"]:
            if element not in content_lower:
                violations.append(
                    {
                        "type": "MISSING_UI_ELEMENT",
                        "pattern": element,
                        "description": f"Missing required UI element: {element}",
                        "file": file_path,
                        "severity": "CRITICAL",
                    }
                )

        return violations

    def validate_template_include(self, content: str, file_path: str) -> bool:
        """Validate that template uses proper includes"""
        # Check if file should use unified mapping modal
        if "mapping" in content.lower() and "modal" in content.lower():
            if self.UNIFIED_MAPPING_MODAL["required_include"] not in content:
                return False
        return True

    def get_violations(self) -> List[Dict[str, str]]:
        """Get all violations"""
        return self.violations

    def get_warnings(self) -> List[Dict[str, str]]:
        """Get all warnings"""
        return self.warnings

    def clear_violations(self):
        """Clear violations and warnings"""
        self.violations = []
        self.warnings = []


# Global guardrails instance
_ui_guardrails = UIPatternGuardrails()


def check_ui_pattern_operation(file_path: str, content: str = None) -> bool:
    """
    Check if UI pattern operation is allowed
    Returns True if allowed, False if violation
    """
    if content:
        violations = _ui_guardrails.check_ui_pattern_compliance(content, file_path)
        if violations:
            _ui_guardrails.violations.extend(violations)
            return False
    return True


def get_ui_guardrails_report() -> Dict[str, Any]:
    """Get UI guardrails violations report"""
    return {
        "violations": _ui_guardrails.get_violations(),
        "warnings": _ui_guardrails.get_warnings(),
        "status": "CRITICAL" if _ui_guardrails.get_violations() else "OK",
    }


def enforce_ui_guardrails():
    """
    Enforce UI guardrails - raise exception if violations found
    """
    violations = _ui_guardrails.get_violations()
    if violations:
        error_msg = "UI PATTERN GUARDRAILS VIOLATIONS DETECTED:\n\n"
        for violation in violations:
            error_msg += f"❌ {violation['type']}: {violation['description']}\n"
            error_msg += f"   File: {violation['file']}\n"
            error_msg += f"   Pattern: {violation['pattern']}\n"
            error_msg += f"   Severity: {violation['severity']}\n\n"

        error_msg += "🚫 ZERO TOLERANCE POLICY VIOLATED\n"
        error_msg += "🚫 IMMEDIATE ACTION REQUIRED\n"
        error_msg += "🚫 SESSION TERMINATION IMMINENT\n"
        error_msg += "🚫 MUST USE unified_mapping_modal.html EXACTLY\n"

        raise RuntimeError(error_msg)


# Auto-enforce on import
if "pytest" not in sys.modules:
    enforce_ui_guardrails()
