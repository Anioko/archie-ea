"""
Custom Fields System for Application Management

Allows administrators to dynamically add custom fields to applications
without requiring database migrations.
"""

import json
import logging
from datetime import datetime

from .. import db
from .mixins import TenantMixin

logger = logging.getLogger(__name__)


class CustomFieldDefinition(db.Model):
    """
    Defines custom fields that can be added to applications.
    Administrators can create new fields on-the-fly.
    """

    __tablename__ = "custom_field_definitions"

    id = db.Column(db.Integer, primary_key=True)

    # Field Metadata
    field_name = db.Column(db.String(100), nullable=False, unique=True)
    field_label = db.Column(db.String(200), nullable=False)
    field_type = db.Column(
        db.String(50), nullable=False
    )  # text, textarea, number, date, select, multiselect, checkbox, url, email
    help_text = db.Column(db.Text)

    # Field Configuration
    is_required = db.Column(db.Boolean, default=False)
    is_searchable = db.Column(db.Boolean, default=True)
    is_shown_in_list = db.Column(db.Boolean, default=False)
    default_value = db.Column(db.Text)

    # For select/multiselect types - stored as JSON array
    options = db.Column(db.Text)  # JSON: ["Option 1", "Option 2"]

    # Validation Rules
    min_value = db.Column(db.Float)
    max_value = db.Column(db.Float)
    min_length = db.Column(db.Integer)
    max_length = db.Column(db.Integer)
    regex_pattern = db.Column(db.String(500))

    # Display Order
    display_order = db.Column(db.Integer, default=0)

    # Entity Type (for future expansion)
    entity_type = db.Column(db.String(50), default="application_component")

    # Grouping
    field_group = db.Column(db.String(100))  # "Business", "Technical", "Lifecycle", etc.

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    values = db.relationship(
        "ApplicationCustomFieldValue",
        backref="field_definition",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def get_options(self):
        """Parse JSON options for select/multiselect fields"""
        if self.options:
            try:
                return json.loads(self.options)
            except (ValueError, KeyError, TypeError):
                return []
        return []

    def set_options(self, options_list):
        """Set options as JSON for select/multiselect fields"""
        self.options = json.dumps(options_list)

    def __repr__(self):
        return f"<CustomFieldDefinition {self.field_name}: {self.field_label}>"


class ApplicationCustomFieldValue(TenantMixin, db.Model):
    """
    Stores the actual values of custom fields for each application.
    Uses a flexible value storage approach (EAV pattern).
    """

    __tablename__ = "application_custom_field_values"

    id = db.Column(db.Integer, primary_key=True)

    # Foreign Keys
    application_component_id = db.Column(
        db.Integer, db.ForeignKey("application_components.id"), nullable=False
    )
    field_definition_id = db.Column(
        db.Integer, db.ForeignKey("custom_field_definitions.id"), nullable=False
    )

    # Value Storage (polymorphic - store different types)
    value_text = db.Column(db.Text)
    value_number = db.Column(db.Float)
    value_date = db.Column(db.Date)
    value_boolean = db.Column(db.Boolean)
    value_json = db.Column(db.Text)  # For arrays/complex data (multiselect, etc.)

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    application = db.relationship("ApplicationComponent", backref="custom_field_values")

    # Unique constraint: one value per field per application
    __table_args__ = (
        db.UniqueConstraint(
            "application_component_id", "field_definition_id", name="uix_app_field"
        ),
    )

    def get_value(self):
        """Get the value based on field type"""
        field_def = self.field_definition
        if not field_def:
            return None

        if field_def.field_type in ["text", "textarea", "url", "email", "select"]:
            return self.value_text
        elif field_def.field_type == "number":
            return self.value_number
        elif field_def.field_type == "date":
            return self.value_date
        elif field_def.field_type == "checkbox":
            return self.value_boolean
        elif field_def.field_type == "multiselect":
            if self.value_json:
                try:
                    return json.loads(self.value_json)
                except (ValueError, KeyError, TypeError):
                    return []
            return []
        return None

    def set_value(self, value, field_type):
        """Set the value based on field type"""
        # Clear all value fields first
        self.value_text = None
        self.value_number = None
        self.value_date = None
        self.value_boolean = None
        self.value_json = None

        if value is None or value == "":
            return

        if field_type in ["text", "textarea", "url", "email", "select"]:
            self.value_text = str(value)
        elif field_type == "number":
            self.value_number = float(value)
        elif field_type == "date":
            self.value_date = value
        elif field_type == "checkbox":
            self.value_boolean = bool(value)
        elif field_type == "multiselect":
            if isinstance(value, list):
                self.value_json = json.dumps(value)
            else:
                self.value_json = json.dumps([value])

    def __repr__(self):
        return f"<ApplicationCustomFieldValue app={self.application_component_id} field={self.field_definition_id}>"
