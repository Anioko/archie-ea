"""Validation schemas for template operations.

Uses Marshmallow for request/response validation.
Follows Data Transfer Object (DTO) pattern.
"""

from marshmallow import Schema, ValidationError, fields, validate, validates_schema


class TemplateQuerySchema(Schema):
    """Schema for template query parameters."""

    framework = fields.Str(allow_none=True)
    layer = fields.Str(
        validate=validate.OneOf(
            [
                "strategy",
                "business",
                "application",
                "technology",
                "physical",
                "motivation",
                "implementation",
            ]
        ),
        allow_none=True,
    )
    element_type = fields.Str(allow_none=True)
    category = fields.Str(allow_none=True)
    search = fields.Str(allow_none=True)
    application_type = fields.Str(allow_none=True)
    limit = fields.Int(validate=validate.Range(min=1, max=1000), load_default=100)
    offset = fields.Int(validate=validate.Range(min=0), load_default=0)


class TemplateCustomizationSchema(Schema):
    """Schema for template customization."""

    name = fields.Str(validate=validate.Length(min=1, max=255), allow_none=True)
    description = fields.Str(allow_none=True)
    properties = fields.Dict(keys=fields.Str(), values=fields.Raw(), allow_none=True)


class InstantiateTemplateSchema(Schema):
    """Schema for single template instantiation."""

    template_id = fields.Str(required=True)  # Accept string to handle large CockroachDB IDs
    application_id = fields.Int(required=True, validate=validate.Range(min=1))
    customizations = fields.Nested(TemplateCustomizationSchema, allow_none=True)
    create_relationships = fields.Bool(load_default=True)


class BulkInstantiateTemplateSchema(Schema):
    """Schema for bulk template instantiation."""

    template_ids = fields.List(
        fields.Str(),  # Accept strings to handle large CockroachDB IDs
        required=True,
        validate=validate.Length(min=1, max=50),  # Limit bulk operations
    )
    customizations = fields.Dict(
        keys=fields.Str(), values=fields.Nested(TemplateCustomizationSchema), allow_none=True
    )
    create_relationships = fields.Bool(load_default=True)

    @validates_schema
    def validate_customizations(self, data, **kwargs):
        """Validate customizations match template_ids."""
        if data.get("customizations"):
            template_ids = set(str(tid) for tid in data["template_ids"])
            custom_keys = set(data["customizations"].keys())

            invalid_keys = custom_keys - template_ids
            if invalid_keys:
                raise ValidationError(
                    f"Customizations contain invalid template IDs: {invalid_keys}",
                    field_name="customizations",
                )


class RemoveTemplateUsageSchema(Schema):
    """Schema for removing template usage."""

    application_id = fields.Int(required=True, validate=validate.Range(min=1))
    template_id = fields.Int(required=True, validate=validate.Range(min=1))
    delete_element = fields.Bool(load_default=True)


class TemplateResponseSchema(Schema):
    """Schema for template response."""

    id = fields.Int()
    framework = fields.Str()
    category = fields.Str()
    subcategory = fields.Str()
    name = fields.Str()
    code = fields.Str()
    element_type = fields.Str()
    layer = fields.Str()
    description = fields.Str()
    level = fields.Int()
    parent_code = fields.Str()
    keywords = fields.List(fields.Str())
    application_types = fields.List(fields.Str())
    usage_count = fields.Int()
    is_active = fields.Bool()


class InstantiationResultSchema(Schema):
    """Schema for instantiation result."""

    success = fields.Bool()
    element = fields.Dict(allow_none=True)
    error = fields.Str(allow_none=True)
    message = fields.Str()


class BulkInstantiationResultSchema(Schema):
    """Schema for bulk instantiation result."""

    success = fields.Bool()
    count = fields.Int()
    elements = fields.List(fields.Dict())
    errors = fields.List(fields.Dict())
    message = fields.Str()
