"""Element Template Models for Framework-Based ArchiMate Element Seeding.

This module provides reusable ArchiMate element templates from standard frameworks
like PCF (Process Classification Framework), ITIL, COBIT, APQC, TOGAF, etc.

Templates allow users to select pre-defined, standardized elements instead of
generating them via AI, ensuring:
- Enterprise-wide consistency
- Zero API costs
- Instant selection
- Alignment with industry frameworks
- Traceability and governance
"""

from datetime import datetime

from app import db

# PostgreSQL-specific imports
try:
    from sqlalchemy.dialects.postgresql import TSVECTOR

    HAS_TSVECTOR = True
except ImportError:
    # SQLite fallback - TSVECTOR not available
    TSVECTOR = None
    HAS_TSVECTOR = False


class ElementTemplate(db.Model):
    """Reusable ArchiMate element templates from standard frameworks.

    Represents a template element from industry frameworks (PCF, ITIL, COBIT, etc.)
    that can be instantiated multiple times across different applications.

    Examples:
        - PCF Process "1.1.1 - Assess external environment"
        - ITIL Practice "Incident Management"
        - COBIT Process "APO01 - Manage IT Management Framework"
    """

    __tablename__ = "element_templates"

    id = db.Column(db.BigInteger, primary_key=True)

    # Framework identification
    framework = db.Column(db.String(50), nullable=False, index=True)
    """Framework source: PCF, ITIL, COBIT, APQC, TOGAF, VALUE_CHAIN, CUSTOM"""

    category = db.Column(db.String(200), index=True)
    """Framework category/group (e.g., 'Develop Vision and Strategy', 'Service Management')"""

    subcategory = db.Column(db.String(200))
    """Framework subcategory for hierarchical organization"""

    # Element identification
    name = db.Column(db.String(255), nullable=False, index=True)
    """Element name (e.g., 'Assess external environment')"""

    code = db.Column(db.String(50), index=True)
    """Framework code (e.g., PCF: '1.1.1', COBIT: 'APO01')"""

    version = db.Column(db.String(20), default="1.0")
    """Framework version (e.g., 'PCF 8.0', 'ITIL 4', 'COBIT 2019')"""

    element_type = db.Column(db.String(50), nullable=False, index=True)
    """ArchiMate element type: BusinessProcess, ApplicationService, TechnologyService, etc."""

    layer = db.Column(db.String(50), nullable=False, index=True)
    """ArchiMate layer: strategy, business, application, technology, motivation, implementation"""

    # Content
    description = db.Column(db.Text)
    """Detailed description of the element"""

    level = db.Column(db.Integer, default=1)
    """Hierarchy level in framework (1=top level, 2=second level, etc.)"""

    parent_code = db.Column(db.String(50), index=True)
    """Parent element code for hierarchical relationships (e.g., '1.1' is parent of '1.1.1')"""

    # Metadata for smart suggestions
    default_properties = db.Column(db.Text)
    """JSON: Default properties for instantiated elements {"priority": "high", "criticality": "core"}"""

    suggested_relationships = db.Column(db.Text)
    """JSON: Suggested relationships when instantiated [{"type": "realization", "target_type": "ApplicationService"}]"""

    keywords = db.Column(db.Text)
    """Comma-separated keywords for search (e.g., 'strategy, planning, vision')"""

    application_types = db.Column(db.Text)
    """Comma-separated application types this template is relevant for (e.g., 'ERP, CRM, SCM')"""

    # Usage tracking
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    """Whether this template is available for use"""

    is_custom = db.Column(db.Boolean, default=False, nullable=False, index=True)
    """Whether this is a custom user-created template (not from standard framework)"""

    usage_count = db.Column(db.Integer, default=0, nullable=False)
    """Number of times this template has been instantiated"""

    last_used_at = db.Column(db.DateTime)
    """Timestamp of last instantiation"""

    # Audit fields
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Relationships
    usages = db.relationship(
        "ElementTemplateUsage", backref="template", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f'<ElementTemplate {self.framework}:{self.code} "{self.name}">'

    def to_dict(self):
        """Convert template to dictionary for API responses."""
        return {
            "id": str(self.id),  # Convert to string to avoid JS precision loss
            "framework": self.framework,
            "category": self.category,
            "subcategory": self.subcategory,
            "name": self.name,
            "code": self.code,
            "version": self.version,
            "element_type": self.element_type,
            "layer": self.layer,
            "description": self.description,
            "level": self.level,
            "parent_code": self.parent_code,
            "keywords": self.keywords.split(",") if self.keywords else [],
            "application_types": self.application_types.split(",")
            if self.application_types
            else [],
            "usage_count": self.usage_count,
            "is_active": self.is_active,
        }

    @staticmethod
    def get_frameworks():
        """Get list of available frameworks dynamically from database."""
        frameworks = (
            db.session.query(ElementTemplate.framework)
            .filter_by(is_active=True)
            .distinct()
            .order_by(ElementTemplate.framework)
            .all()
        )
        return [f[0] for f in frameworks if f[0]]

    @staticmethod
    def get_categories(framework):
        """Get categories for a specific framework."""
        return (
            db.session.query(ElementTemplate.category)
            .filter_by(framework=framework, is_active=True)
            .distinct()
            .order_by(ElementTemplate.category)
            .all()
        )


class ElementTemplateUsage(db.Model):
    """Track instantiation of element templates for specific applications.

    This table maintains the many-to-many relationship between templates and
    applications, allowing us to:
    - Track which templates are used by which applications
    - Prevent duplicate instantiations
    - Provide usage analytics
    - Enable "remove template" functionality
    """

    __tablename__ = "element_template_usage"

    id = db.Column(db.BigInteger, primary_key=True)

    # Template reference
    template_id = db.Column(
        db.BigInteger,
        db.ForeignKey("element_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    """Reference to the template that was instantiated"""

    # Application reference
    application_id = db.Column(
        db.BigInteger,
        db.ForeignKey("application_components.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    """Application this template was instantiated for"""

    # Created element reference
    archimate_element_id = db.Column(
        db.BigInteger,
        db.ForeignKey("archimate_elements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    """The ArchiMate element created from this template"""

    # Link-only flag
    link_only = db.Column(db.Boolean, default=False, nullable=False, index=True)
    """True if this is only a link to an existing element (not a new instantiation)"""

    # Domain model reference (optional - depends on element type)
    domain_model_type = db.Column(db.String(50))
    """Type of domain model created (BusinessProcess, ApplicationService, etc.)"""

    domain_model_id = db.Column(db.BigInteger)
    """ID of the domain-specific model instance"""

    # Customizations applied during instantiation
    customizations_applied = db.Column(db.Text)
    """JSON: Customizations made to template (e.g., {"name": "Custom Name", "priority": "critical"})"""

    # Additional metadata
    notes = db.Column(db.Text)
    """Optional notes about this template instantiation"""

    instantiated_element_id = db.Column(db.BigInteger)
    """Legacy field - use archimate_element_id instead"""

    # Audit fields
    instantiated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    instantiated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    """Alias for instantiated_by for consistency"""

    # Relationships
    element = db.relationship(
        "ArchiMateElement", backref="template_usage", foreign_keys=[archimate_element_id]
    )
    archimate_element = db.relationship(
        "ArchiMateElement", foreign_keys=[archimate_element_id], overlaps="element,template_usage"
    )
    application = db.relationship(
        "ApplicationComponent", backref="template_usages", foreign_keys=[application_id]
    )
    user = db.relationship("User", backref="template_usages", foreign_keys=[instantiated_by])

    # Composite unique constraint: prevent duplicate template usage per application
    __table_args__ = (
        db.UniqueConstraint("template_id", "application_id", name="uq_template_application"),
        db.Index("ix_element_template_usage_app_template", "application_id", "template_id"),
    )

    def __repr__(self):
        return f"<ElementTemplateUsage template={self.template_id} app={self.application_id}>"

    def to_dict(self):
        """Convert usage to dictionary for API responses."""
        return {
            "id": self.id,
            "template_id": self.template_id,
            "application_id": self.application_id,
            "archimate_element_id": self.archimate_element_id,
            "domain_model_type": self.domain_model_type,
            "domain_model_id": self.domain_model_id,
            "instantiated_at": self.instantiated_at.isoformat() if self.instantiated_at else None,
            "instantiated_by": self.instantiated_by,
        }


class ElementTemplateRecommendation(db.Model):
    """AI-powered or rule-based recommendations for element templates.

    Suggests relevant templates based on:
    - Application type (ERP suggests O2C, P2P processes)
    - Technology stack (Java suggests deployment artifacts)
    - Industry (Healthcare suggests HIPAA compliance processes)
    - Similar applications (pattern matching)
    """

    __tablename__ = "element_template_recommendations"

    id = db.Column(db.BigInteger, primary_key=True)

    # Recommendation trigger
    trigger_type = db.Column(db.String(50), nullable=False)
    """Type of trigger: application_type, tech_stack, industry, similar_app, keyword"""

    trigger_value = db.Column(db.String(100), nullable=False, index=True)
    """Value that triggers recommendation (e.g., 'ERP', 'Java', 'Healthcare')"""

    # Recommended template
    template_id = db.Column(
        db.BigInteger,
        db.ForeignKey("element_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Recommendation metadata
    relevance_score = db.Column(db.Float, default=1.0)
    """Relevance score 0 - 1 (higher = more relevant)"""

    reason = db.Column(db.String(500))
    """Human-readable reason for recommendation"""

    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Relationships
    template = db.relationship("ElementTemplate", backref="recommendations")

    __table_args__ = (
        db.Index("ix_template_recommendations_trigger", "trigger_type", "trigger_value"),
    )

    def __repr__(self):
        return f"<ElementTemplateRecommendation {self.trigger_type}:{self.trigger_value} -> template={self.template_id}>"


# Export all models
__all__ = ["ElementTemplate", "ElementTemplateUsage", "ElementTemplateRecommendation"]
