"""
Artifact Validator - Prevents silent failures by validating ALL generated artifacts.

This is the #1 defense against LLM hallucinations breaking your pipeline.
EVERY stage MUST produce artifacts. Zero artifacts = FAILURE.
"""
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validation check."""

    valid: bool
    message: str = ""
    warnings: List[str] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []

    def add_error(self, error: str):
        """Add an error to the result."""
        self.errors.append(error)
        self.valid = False

    def add_warning(self, warning: str):
        """Add a warning to the result."""
        self.warnings.append(warning)


class ArtifactValidator:
    """
    Validates generated artifacts to prevent silent failures.
    Catches issues BEFORE they propagate through the pipeline.
    """

    # Placeholder text that indicates LLM hallucination
    PLACEHOLDER_PATTERNS = [
        "tbd",
        "todo",
        "fixme",
        "xxx",
        "placeholder",
        "to be determined",
        "to be defined",
        "not implemented",
        "coming soon",
        "example",
        "sample",
        "dummy",
    ]

    @staticmethod
    def validate_architecture_elements(elements: List[Dict]) -> ValidationResult:
        """
        Validate ArchiMate elements from LLM.

        Rules:
        1. Must have at least 1 element
        2. Each element must have: name, type, layer, description
        3. No placeholder text in descriptions
        4. Element types must be valid ArchiMate types
        5. Layers must be valid ArchiMate layers

        Args:
            elements: List of element dictionaries

        Returns:
            ValidationResult with detailed errors/warnings
        """
        result = ValidationResult(valid=True, message="Architecture elements validated")

        # Rule 1: Must have elements
        if not elements:
            result.add_error("ZERO ELEMENTS GENERATED - Pipeline cannot proceed without artifacts")
            return result

        if len(elements) == 0:
            result.add_error("Empty elements list")
            return result

        # Valid ArchiMate types
        VALID_TYPES = {
            "BusinessActor",
            "BusinessRole",
            "BusinessProcess",
            "BusinessService",
            "BusinessFunction",
            "BusinessObject",
            "BusinessCapability",
            "ApplicationComponent",
            "ApplicationService",
            "ApplicationInterface",
            "ApplicationFunction",
            "DataObject",
            "TechnologyService",
            "TechnologyComponent",
            "Artifact",
            "Node",
            "Device",
            "SystemSoftware",
            "CommunicationNetwork",
            "Stakeholder",
            "Driver",
            "Assessment",
            "Goal",
            "Outcome",
            "Principle",
            "Requirement",
            "Constraint",
        }

        VALID_LAYERS = {
            "Business",
            "Application",
            "Technology",
            "Motivation",
            "Strategy",
            "Implementation",
            "Physical",
        }

        for idx, elem in enumerate(elements):
            elem_ref = f"Element #{idx + 1}"

            # Rule 2: Required fields
            if not isinstance(elem, dict):
                result.add_error(f"{elem_ref}: Not a dictionary")
                continue

            name = elem.get("name", "").strip()
            elem_type = elem.get("type", "").strip()
            layer = elem.get("layer", "").strip()
            description = elem.get("description", "").strip()

            if not name:
                result.add_error(f"{elem_ref}: Missing 'name' field")
            elif len(name) < 3:
                result.add_error(f"{elem_ref}: Name too short (< 3 chars): '{name}'")

            if not elem_type:
                result.add_error(f"{elem_ref} ({name}): Missing 'type' field")
            elif elem_type not in VALID_TYPES:
                result.add_error(f"{elem_ref} ({name}): Invalid type '{elem_type}'")

            if not layer:
                result.add_error(f"{elem_ref} ({name}): Missing 'layer' field")
            elif layer not in VALID_LAYERS:
                result.add_error(f"{elem_ref} ({name}): Invalid layer '{layer}'")

            if not description:
                result.add_warning(f"{elem_ref} ({name}): Missing description")
            elif len(description) < 20:
                result.add_warning(f"{elem_ref} ({name}): Description too short (< 20 chars)")

            # Rule 3: No placeholder text
            if description and ArtifactValidator._has_placeholder_text(description):
                result.add_error(
                    f"{elem_ref} ({name}): Contains placeholder text in description: '{description[:50]}...'"
                )

        # Summary
        if result.valid:
            result.message = f"✓ Validated {len(elements)} architecture elements successfully"
            if result.warnings:
                result.message += f" ({len(result.warnings)} warnings)"
        else:
            result.message = f"✗ Architecture validation failed with {len(result.errors)} errors"

        return result

    @staticmethod
    def validate_requirements(requirements: List[Dict]) -> ValidationResult:
        """
        Validate generated requirements.

        Rules:
        1. Must have at least 1 requirement
        2. Each must have: description, category, priority
        3. No placeholder text
        4. Requirements must be testable (have measurable criteria)
        """
        result = ValidationResult(valid=True, message="Requirements validated")

        if not requirements or len(requirements) == 0:
            result.add_error("ZERO REQUIREMENTS GENERATED")
            return result

        VALID_CATEGORIES = {"functional", "non-functional", "business", "technical", "security"}
        VALID_PRIORITIES = {"low", "medium", "high", "critical"}

        for idx, req in enumerate(requirements):
            req_ref = f"Requirement #{idx + 1}"

            if not isinstance(req, dict):
                result.add_error(f"{req_ref}: Not a dictionary")
                continue

            description = req.get("description", "").strip()
            category = req.get("category", "").strip().lower()
            priority = req.get("priority", "").strip().lower()

            if not description:
                result.add_error(f"{req_ref}: Missing description")
            elif len(description) < 10:
                result.add_error(f"{req_ref}: Description too short")
            elif ArtifactValidator._has_placeholder_text(description):
                result.add_error(f"{req_ref}: Contains placeholder text")

            if category and category not in VALID_CATEGORIES:
                result.add_warning(f"{req_ref}: Unknown category '{category}'")

            if priority and priority not in VALID_PRIORITIES:
                result.add_warning(f"{req_ref}: Unknown priority '{priority}'")

            # Check if requirement is testable
            if not ArtifactValidator._is_testable(description):
                result.add_warning(f"{req_ref}: Not testable - lacks measurable criteria")

        if result.valid:
            result.message = f"✓ Validated {len(requirements)} requirements"
        else:
            result.message = f"✗ Requirements validation failed"

        return result

    @staticmethod
    def validate_code_artifacts(artifacts: List[Dict]) -> ValidationResult:
        """
        Validate generated code artifacts.

        Rules:
        1. Must have at least 1 artifact
        2. Each must have: filename, content
        3. No placeholder text in code
        4. Code must be non-empty (> 50 chars)
        5. Filenames must have valid extensions
        """
        result = ValidationResult(valid=True, message="Code artifacts validated")

        if not artifacts or len(artifacts) == 0:
            result.add_error("ZERO CODE ARTIFACTS GENERATED")
            return result

        VALID_EXTENSIONS = {".py", ".java", ".js", ".ts", ".cs", ".go", ".rb", ".php", ".sql"}

        for idx, artifact in enumerate(artifacts):
            artifact_ref = f"Artifact #{idx + 1}"

            if not isinstance(artifact, dict):
                result.add_error(f"{artifact_ref}: Not a dictionary")
                continue

            filename = artifact.get("filename", "").strip()
            content = artifact.get("content", "").strip()

            if not filename:
                result.add_error(f"{artifact_ref}: Missing filename")
            else:
                import os

                ext = os.path.splitext(filename)[1]
                if ext not in VALID_EXTENSIONS:
                    result.add_warning(
                        f"{artifact_ref} ({filename}): Unknown file extension '{ext}'"
                    )

            if not content:
                result.add_error(f"{artifact_ref} ({filename}): Empty content")
            elif len(content) < 50:
                result.add_error(f"{artifact_ref} ({filename}): Content too short (< 50 chars)")
            elif ArtifactValidator._has_placeholder_text(content):
                result.add_error(
                    f"{artifact_ref} ({filename}): Contains placeholder text (TODO/FIXME)"
                )

        if result.valid:
            result.message = f"✓ Validated {len(artifacts)} code artifacts"
        else:
            result.message = f"✗ Code validation failed"

        return result

    @staticmethod
    def validate_json_response(
        response_text: str, expected_keys: Optional[List[str]] = None
    ) -> ValidationResult:
        """
        Validate LLM JSON response.

        Rules:
        1. Must be valid JSON
        2. Must contain expected keys
        3. Must not be empty

        Args:
            response_text: Raw LLM response
            expected_keys: Keys that must be present in JSON

        Returns:
            ValidationResult with parsed JSON in result.data if valid
        """
        result = ValidationResult(valid=True, message="JSON response validated")

        # Strip markdown code blocks
        import re

        json_match = re.search(r"```(?:json)?\n(.*?)\n```", response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)

        # Try to parse JSON
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            result.add_error(f"Invalid JSON: {str(e)}")
            result.add_error(f"Response preview: {response_text[:200]}...")
            return result

        # Check expected keys
        if expected_keys:
            missing_keys = [key for key in expected_keys if key not in data]
            if missing_keys:
                result.add_error(f"Missing required keys: {', '.join(missing_keys)}")

        # Check not empty
        if isinstance(data, dict) and len(data) == 0:
            result.add_error("Empty JSON object")
        elif isinstance(data, list) and len(data) == 0:
            result.add_error("Empty JSON array")

        # Attach parsed data
        if result.valid:
            result.data = data
            result.message = "✓ Valid JSON response"

        return result

    @staticmethod
    def _has_placeholder_text(text: str) -> bool:
        """Check if text contains placeholder patterns."""
        text_lower = text.lower()
        return any(pattern in text_lower for pattern in ArtifactValidator.PLACEHOLDER_PATTERNS)

    @staticmethod
    def _is_testable(requirement_text: str) -> bool:
        """
        Check if requirement is testable (has measurable criteria).

        Testable requirements contain keywords like:
        - shall, must, will, should
        - measurable quantities: within X seconds, at least N users
        - specific values: equals, greater than, less than
        """
        text_lower = requirement_text.lower()

        testable_keywords = [
            "must",
            "shall",
            "will",
            "should",
            "within",
            "at least",
            "no more than",
            "maximum",
            "minimum",
            "greater than",
            "less than",
            "equal to",
            "respond in",
            "process within",
            "support up to",
        ]

        return any(keyword in text_lower for keyword in testable_keywords)


# Convenience function for quick validation
def validate_or_fail(artifacts: List[Any], validator_func) -> List[Any]:
    """
    Validate artifacts and raise exception if validation fails.
    Use this for fail-fast behavior in pipelines.

    Args:
        artifacts: List of artifacts to validate
        validator_func: Validation function to call

    Returns:
        artifacts if validation passes

    Raises:
        ValueError: If validation fails
    """
    result = validator_func(artifacts)

    if not result.valid:
        error_msg = f"{result.message}\n" + "\n".join(result.errors)
        logger.error(f"Artifact validation failed: {error_msg}")
        raise ValueError(error_msg)

    if result.warnings:
        for warning in result.warnings:
            logger.warning(f"Artifact warning: {warning}")

    logger.info(result.message)
    return artifacts
