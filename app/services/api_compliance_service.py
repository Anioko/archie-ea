"""
API Compliance Enforcement Service

MANDATORY: All LLM agents must validate API compliance before creating endpoints.
This service enforces the API documentation standards.
"""

import re
from typing import Dict, List, Optional

from flask import current_app


class APIComplianceService:
    """
    Enforces API documentation compliance for all endpoints.

    MANDATORY: All API work must pass through this validation.
    """

    # Blueprint URL prefixes from docs/API_DOCUMENTATION.md
    VALID_BLUEPRINT_PREFIXES = {
        "application_mgmt": "/dashboard",
        "vendors": "/vendors",
        "vendors_api": "/api/vendors",
        "enterprise_architecture": "/api/enterprise",
        "ai_chat": "/ai-chat",
        "capability_framework": "/capability-framework",
        "dynamic_dashboards": "/auto-dashboard",
        "framework_config_ui": "/framework-config",
        "strategic": "/strategic",
    }

    # Forbidden URL patterns
    FORBIDDEN_PATTERNS = [
        r"/application-mgmt/",  # Should be /dashboard
        r"/get_",  # Should be RESTful GET /resource
        r"/delete_",  # Should be RESTful DELETE /resource
        r"/create_",  # Should be RESTful POST /resource
        r"/update_",  # Should be RESTful PUT /resource
    ]

    # Required response format
    REQUIRED_RESPONSE_FIELDS = ["success"]

    @classmethod
    def validate_blueprint_url(cls, blueprint_name: str, url_prefix: str) -> Dict[str, any]:
        """
        Validate blueprint URL prefix compliance.

        Args:
            blueprint_name: Name of the blueprint
            url_prefix: URL prefix from blueprint definition

        Returns:
            Dict with validation result
        """
        if blueprint_name in cls.VALID_BLUEPRINT_PREFIXES:
            expected_prefix = cls.VALID_BLUEPRINT_PREFIXES[blueprint_name]
            if url_prefix != expected_prefix:
                return {
                    "valid": False,
                    "error": f'Blueprint {blueprint_name} must use url_prefix="{expected_prefix}", not "{url_prefix}"',
                    "violation": "BLUEPRINT_PREFIX_MISMATCH",
                }

        return {"valid": True}

    @classmethod
    def validate_route_url(cls, route_url: str, blueprint_name: str) -> Dict[str, any]:
        """
        Validate individual route URL compliance.

        Args:
            route_url: The route URL pattern
            blueprint_name: Name of the blueprint

        Returns:
            Dict with validation result
        """
        # Check forbidden patterns
        for pattern in cls.FORBIDDEN_PATTERNS:
            if re.search(pattern, route_url):
                return {
                    "valid": False,
                    "error": f'Route URL "{route_url}" contains forbidden pattern "{pattern}"',
                    "violation": "FORBIDDEN_URL_PATTERN",
                    "suggestion": "Use RESTful patterns: GET /resource, POST /resource, PUT /resource/:id, DELETE /resource/:id",
                }

        # Check if route uses blueprint name incorrectly
        if f"/{blueprint_name}/" in route_url:
            return {
                "valid": False,
                "error": f'Route URL "{route_url}" incorrectly includes blueprint name "{blueprint_name}"',
                "violation": "BLUEPRINT_NAME_IN_URL",
                "suggestion": f"Remove blueprint name from URL. Use blueprint url_prefix instead.",
            }

        return {"valid": True}

    @classmethod
    def validate_response_format(cls, response_data: Dict) -> Dict[str, any]:
        """
        Validate API response format compliance.

        Args:
            response_data: Response dictionary

        Returns:
            Dict with validation result
        """
        if not isinstance(response_data, dict):
            return {
                "valid": False,
                "error": "Response must be a dictionary",
                "violation": "INVALID_RESPONSE_TYPE",
            }

        # Check required fields
        for field in cls.REQUIRED_RESPONSE_FIELDS:
            if field not in response_data:
                return {
                    "valid": False,
                    "error": f'Response missing required field: "{field}"',
                    "violation": "MISSING_RESPONSE_FIELD",
                }

        # Check error response format
        if not response_data.get("success", True) and "error" not in response_data:
            return {
                "valid": False,
                "error": 'Error responses must include "error" field',
                "violation": "MISSING_ERROR_FIELD",
            }

        return {"valid": True}

    @classmethod
    def validate_api_compliance(
        cls,
        blueprint_name: str,
        url_prefix: str,
        route_url: str,
        response_data: Optional[Dict] = None,
    ) -> Dict[str, any]:
        """
        Complete API compliance validation.

        Args:
            blueprint_name: Name of the blueprint
            url_prefix: URL prefix from blueprint definition
            route_url: Individual route URL
            response_data: Optional response data to validate

        Returns:
            Dict with complete validation result
        """
        violations = []

        # Validate blueprint URL prefix
        blueprint_validation = cls.validate_blueprint_url(blueprint_name, url_prefix)
        if not blueprint_validation["valid"]:
            violations.append(blueprint_validation)

        # Validate route URL
        route_validation = cls.validate_route_url(route_url, blueprint_name)
        if not route_validation["valid"]:
            violations.append(route_validation)

        # Validate response format if provided
        if response_data:
            response_validation = cls.validate_response_format(response_data)
            if not response_validation["valid"]:
                violations.append(response_validation)

        if violations:
            return {
                "valid": False,
                "violations": violations,
                "summary": f"Found {len(violations)} API compliance violations",
            }

        return {"valid": True, "summary": "API compliance validation passed"}

    @classmethod
    def get_correct_url_pattern(cls, blueprint_name: str, resource_name: str) -> str:
        """
        Get the correct URL pattern for a given blueprint and resource.

        Args:
            blueprint_name: Name of the blueprint
            resource_name: Name of the resource (e.g., 'applications', 'vendors')

        Returns:
            Correct URL pattern
        """
        if blueprint_name == "application_mgmt":
            return f"/dashboard/api/{resource_name}"
        elif blueprint_name == "vendors_api":
            return f"/api/vendors/{resource_name}"
        elif blueprint_name == "enterprise_architecture":
            return f"/api/enterprise/{resource_name}"
        elif blueprint_name == "ai_chat":
            return f"/ai-chat/{resource_name}"
        else:
            return f"/{blueprint_name}/{resource_name}"

    @classmethod
    def log_compliance_violation(cls, violation_data: Dict):
        """
        Log API compliance violations for enforcement tracking.

        Args:
            violation_data: Details of the violation
        """
        try:
            current_app.logger.error(f"API COMPLIANCE VIOLATION: {violation_data}")
        except RuntimeError:
            # App context not available, print instead
            print(f"API COMPLIANCE VIOLATION: {violation_data}")


# MANDATORY: All LLM agents must use this validator
def validate_api_endpoint(
    blueprint_name: str, url_prefix: str, route_url: str, response_data: Optional[Dict] = None
) -> bool:
    """
    MANDATORY VALIDATION: All API endpoints must pass this check.

    Args:
        blueprint_name: Name of the blueprint
        url_prefix: URL prefix from blueprint definition
        route_url: Individual route URL
        response_data: Optional response data to validate

    Returns:
        True if compliant, False otherwise

    Raises:
        ValueError: If validation fails with details
    """
    result = APIComplianceService.validate_api_compliance(
        blueprint_name, url_prefix, route_url, response_data
    )

    if not result["valid"]:
        # Log violation
        APIComplianceService.log_compliance_violation(result)

        # Raise error with details
        error_msg = "API COMPLIANCE VIOLATION DETECTED!\n"
        for violation in result["violations"]:
            error_msg += f"- {violation['error']}\n"
            if "suggestion" in violation:
                error_msg += f"  Suggestion: {violation['suggestion']}\n"
        error_msg += f"\nReference: docs/API_DOCUMENTATION.md"

        raise ValueError(error_msg)

    return True
