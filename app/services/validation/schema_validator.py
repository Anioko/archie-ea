"""
JSON Schema Validator for LLM responses.
Validates structure before semantic validation.
"""
import json
import logging
from typing import Any, Dict

from .artifact_validator import ValidationResult

logger = logging.getLogger(__name__)


class SchemaValidator:
    """Validates JSON responses against predefined schemas."""

    # JSON Schema definitions for LLM outputs
    SCHEMAS = {
        "architecture_elements": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["name", "type", "layer"],
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "type": {"type": "string", "minLength": 1},
                    "layer": {"type": "string", "minLength": 1},
                    "description": {"type": "string"},
                },
            },
        },
        "architecture_with_relationships": {
            "type": "object",
            "required": ["elements", "relationships"],
            "properties": {
                "elements": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": ["name", "type", "layer"],
                        "properties": {
                            "name": {"type": "string", "minLength": 1},
                            "type": {"type": "string", "minLength": 1},
                            "layer": {"type": "string", "minLength": 1},
                            "description": {"type": "string"},
                        },
                    },
                },
                "relationships": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["source", "target", "type"],
                        "properties": {
                            "source": {"type": "string", "minLength": 1},
                            "target": {"type": "string", "minLength": 1},
                            "type": {"type": "string", "minLength": 1},
                        },
                    },
                },
            },
        },
        "uml_class_diagram": {
            "type": "object",
            "required": ["classes"],
            "properties": {
                "classes": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": ["name", "type"],
                        "properties": {
                            "name": {"type": "string", "minLength": 1},
                            "type": {"type": "string", "enum": ["class", "interface", "abstract"]},
                            "stereotype": {"type": "string"},
                            "attributes": {"type": "array"},
                            "methods": {"type": "array"},
                        },
                    },
                },
                "relationships": {"type": "array"},
            },
        },
        "requirements": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["description"],
                "properties": {
                    "description": {"type": "string", "minLength": 10},
                    "category": {"type": "string"},
                    "priority": {"type": "string"},
                },
            },
        },
    }

    @staticmethod
    def validate(data: Any, schema_name: str) -> ValidationResult:
        """
        Validate data against named schema.

        Args:
            data: Data to validate (already parsed JSON)
            schema_name: Name of schema to use

        Returns:
            ValidationResult
        """
        result = ValidationResult(
            valid=True, message=f"Schema validation passed for '{schema_name}'"
        )

        schema = SchemaValidator.SCHEMAS.get(schema_name)
        if not schema:
            result.add_error(f"Unknown schema: {schema_name}")
            return result

        # Use jsonschema library if available, otherwise basic validation
        try:
            import jsonschema

            try:
                jsonschema.validate(data, schema)
            except jsonschema.ValidationError as e:
                result.add_error(f"Schema validation failed: {e.message}")
                result.add_error(f"Failed at path: {' -> '.join(str(p) for p in e.path)}")
        except ImportError:
            # Fallback to basic validation
            logger.warning("jsonschema library not installed, using basic validation")
            result = SchemaValidator._basic_validate(data, schema)

        return result

    @staticmethod
    def _basic_validate(data: Any, schema: Dict) -> ValidationResult:
        """Basic schema validation without jsonschema library."""
        result = ValidationResult(valid=True, message="Basic schema validation passed")

        # Validate type
        schema_type = schema.get("type")
        if schema_type == "array" and not isinstance(data, list):
            result.add_error(f"Expected array, got {type(data).__name__}")
        elif schema_type == "object" and not isinstance(data, dict):
            result.add_error(f"Expected object, got {type(data).__name__}")

        # Validate minItems for arrays
        if schema_type == "array" and "minItems" in schema:
            if len(data) < schema["minItems"]:
                result.add_error(f"Array has {len(data)} items, minimum is {schema['minItems']}")

        # Validate required fields for objects
        if schema_type == "object" and "required" in schema:
            if isinstance(data, dict):
                missing = [field for field in schema["required"] if field not in data]
                if missing:
                    result.add_error(f"Missing required fields: {', '.join(missing)}")

        return result

    @staticmethod
    def validate_and_parse(response_text: str, schema_name: str) -> ValidationResult:
        """
        Parse JSON and validate in one step.

        Args:
            response_text: Raw LLM response
            schema_name: Schema to validate against

        Returns:
            ValidationResult with parsed data attached if valid
        """
        result = ValidationResult(valid=True)

        # Strip markdown code blocks
        import re

        json_match = re.search(r"```(?:json)?\n(.*?)\n```", response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)

        # Parse JSON
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            result.add_error(f"Invalid JSON: {str(e)}")
            return result

        # Validate against schema
        validation_result = SchemaValidator.validate(data, schema_name)

        if validation_result.valid:
            result.data = data
            result.message = f"✓ Parsed and validated {schema_name}"
        else:
            result.valid = False
            result.errors = validation_result.errors
            result.message = validation_result.message

        return result
