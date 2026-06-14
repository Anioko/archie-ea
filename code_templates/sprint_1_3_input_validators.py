"""
Input Validation Schemas for Architecture Assistant
Sprint 1.3: Security Hardening

Uses Marshmallow for schema validation and HTML sanitization.

INSTALLATION:
    pip install marshmallow bleach

USAGE:
    from app.validators.architecture_validators import DesignSolutionSchema

    @bp.route('/api/architecture-assistant/design-solution', methods=['POST'])
    @login_required
    def design_solution():
        schema = DesignSolutionSchema()

        try:
            validated_data = schema.load(request.json)
        except ValidationError as e:
            return jsonify({'errors': e.messages}), 400

        # Use validated_data (safe, sanitized)
"""

import re

import bleach
from marshmallow import Schema, ValidationError, fields, validate, validates_schema


class DesignSolutionSchema(Schema):
    """Validate design solution request"""

    session_name = fields.Str(
        required=True,
        validate=validate.Length(min=3, max=200),
        error_messages={
            "required": "Session name is required",
            "invalid": "Session name must be 3 - 200 characters",
        },
    )

    capability_id = fields.Int(
        required=True,
        validate=validate.Range(min=1),
        error_messages={"required": "Capability ID is required"},
    )

    description = fields.Str(validate=validate.Length(max=5000), allow_none=True)

    business_context = fields.Str(validate=validate.Length(max=10000), allow_none=True)

    stakeholders = fields.List(
        fields.Int(validate=validate.Range(min=1)),
        validate=validate.Length(max=50),
        allow_none=True,
    )

    @validates_schema
    def validate_session_name(self, data, **kwargs):
        """Additional validation for session name"""
        name = data.get("session_name", "")

        # No special characters (prevent injection)
        if re.search(r"[<>{}\[\]\\]", name):
            raise ValidationError(
                "Session name contains invalid characters", field_name="session_name"
            )

    def sanitize_html(self, data):
        """Remove potentially harmful HTML from text fields"""
        html_fields = ["description", "business_context"]

        allowed_tags = ["p", "br", "strong", "em", "ul", "ol", "li", "a"]
        allowed_attrs = {"a": ["href", "title"]}

        for field in html_fields:
            if field in data and data[field]:
                data[field] = bleach.clean(
                    data[field], tags=allowed_tags, attributes=allowed_attrs, strip=True
                )

        return data


class GapAnalysisSchema(Schema):
    """Validate gap analysis request"""

    session_id = fields.Int(required=True, validate=validate.Range(min=1))

    current_state = fields.Str(
        required=True,
        validate=validate.Length(min=10, max=5000),
        error_messages={"required": "Current state description is required"},
    )

    desired_state = fields.Str(
        required=True,
        validate=validate.Length(min=10, max=5000),
        error_messages={"required": "Desired state description is required"},
    )

    constraints = fields.List(
        fields.Str(validate=validate.Length(max=500)),
        validate=validate.Length(max=20),
        allow_none=True,
    )


class OptionGenerationSchema(Schema):
    """Validate option generation request"""

    session_id = fields.Int(required=True, validate=validate.Range(min=1))

    preferences = fields.Dict(keys=fields.Str(), values=fields.Str(), allow_none=True)

    budget_range = fields.Dict(
        keys=fields.Str(validate=validate.OneOf(["min", "max"])),
        values=fields.Int(validate=validate.Range(min=0)),
        allow_none=True,
    )


class ADRGenerationSchema(Schema):
    """Validate ADR generation request"""

    session_id = fields.Int(required=True, validate=validate.Range(min=1))

    title = fields.Str(
        validate=validate.Length(min=5, max=200), allow_none=True  # Can be auto-generated
    )

    stakeholders = fields.List(
        fields.Int(validate=validate.Range(min=1)),
        validate=validate.Length(max=50),
        allow_none=True,
    )


# Sanitization utilities


def sanitize_filename(filename):
    """Sanitize filename for safe file operations"""
    # Remove directory traversal attempts
    filename = filename.replace("..", "").replace("/", "").replace("\\", "")

    # Allow only alphanumeric, dash, underscore, dot
    filename = re.sub(r"[^a-zA-Z0 - 9._-]", "", filename)

    # Limit length
    if len(filename) > 255:
        filename = filename[:255]

    return filename


def sanitize_sql_like(value):
    """Escape special characters for SQL LIKE queries"""
    # Escape SQL wildcards
    value = value.replace("%", "\\%").replace("_", "\\_")
    return value


# Example usage in routes:

"""
from app.validators.architecture_validators import (
    DesignSolutionSchema,
    GapAnalysisSchema,
    sanitize_filename
)

@bp.route('/api/architecture-assistant/design-solution', methods=['POST'])
@login_required
def design_solution():
    schema = DesignSolutionSchema()

    try:
        # Validate
        validated_data = schema.load(request.json)

        # Sanitize HTML
        validated_data = schema.sanitize_html(validated_data)

    except ValidationError as e:
        return jsonify({
            'error': 'Validation failed',
            'errors': e.messages
        }), 400

    # Use validated_data safely
    session = assistant_service.create_session(
        data=validated_data,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id
    )

    return jsonify(session.to_dict()), 201
"""
