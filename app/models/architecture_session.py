"""
Architecture Session Model - Track bulk operations for undo capability

ENTERPRISE FEATURE: Allows architects to rollback bulk operations if they make mistakes.

Use Cases:
- Undo "Add 50 elements from framework"
- Rollback if wrong framework selected
- Audit trail for compliance
- Session history view

Example:
    session = ArchitectureSession(
        application_id=123,
        user_id=456,
        operation_type='add_templates'
    )
    db.session.add(session)

    # Track created elements
    session.track_element(element.id)

    # Later, rollback if needed
    session.rollback()
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app import db
from app.models.mixins import TenantMixin


class ArchitectureSession(TenantMixin, db.Model):
    """
    Track bulk architecture operations for undo/rollback capability.

    CRITICAL ENTERPRISE FEATURE: Provides transaction-like behavior for bulk operations.
    """

    __tablename__ = "architecture_sessions"

    id = Column(Integer, primary_key=True)

    # Session Context
    application_id = Column(
        Integer, ForeignKey("application_components.id"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Operation Details
    operation_type = Column(
        String(50), nullable=False
    )  # 'add_templates', 'link_templates', 'bulk_delete'
    operation_description = Column(String(500))  # Human-readable description

    # Tracking
    created_elements = Column(JSON)  # List of created ArchiMateElement IDs
    created_relationships = Column(JSON)  # List of created ArchiMateRelationship IDs
    created_domain_objects = Column(JSON)  # List of domain model IDs (ApplicationComponent, etc.)

    # Metadata
    framework = Column(String(50))  # Framework used (PCF, TOGAF, etc.)
    template_count = Column(Integer)  # Number of templates instantiated

    # Status
    rolled_back = Column(Boolean, default=False, nullable=False)
    rollback_at = Column(DateTime)
    rollback_reason = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    application = relationship("ApplicationComponent", backref="architecture_sessions")
    user = relationship("User", backref="architecture_sessions")

    def __init__(
        self,
        application_id,
        user_id,
        operation_type,
        operation_description=None,
        framework=None,
        template_count=None,
    ):
        self.application_id = application_id
        self.user_id = user_id
        self.operation_type = operation_type
        self.operation_description = operation_description
        self.framework = framework
        self.template_count = template_count
        self.created_elements = []
        self.created_relationships = []
        self.created_domain_objects = []

    def track_element(self, element_id):
        """Add an ArchiMateElement ID to tracking list"""
        if self.created_elements is None:
            self.created_elements = []
        if element_id not in self.created_elements:
            self.created_elements.append(element_id)

    def track_relationship(self, relationship_id):
        """Add an ArchiMateRelationship ID to tracking list"""
        if self.created_relationships is None:
            self.created_relationships = []
        if relationship_id not in self.created_relationships:
            self.created_relationships.append(relationship_id)

    def track_domain_object(self, obj_type, obj_id):
        """Add a domain model object to tracking list"""
        if self.created_domain_objects is None:
            self.created_domain_objects = []
        self.created_domain_objects.append({"type": obj_type, "id": obj_id})

    def get_summary(self):
        """Get human-readable summary of session"""
        return {
            "id": self.id,
            "operation_type": self.operation_type,
            "description": self.operation_description,
            "elements_created": len(self.created_elements or []),
            "relationships_created": len(self.created_relationships or []),
            "framework": self.framework,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "rolled_back": self.rolled_back,
            "can_rollback": not self.rolled_back,
        }

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "application_id": self.application_id,
            "user_id": self.user_id,
            "operation_type": self.operation_type,
            "operation_description": self.operation_description,
            "created_elements": self.created_elements or [],
            "created_relationships": self.created_relationships or [],
            "created_domain_objects": self.created_domain_objects or [],
            "framework": self.framework,
            "template_count": self.template_count,
            "rolled_back": self.rolled_back,
            "rollback_at": self.rollback_at.isoformat() if self.rollback_at else None,
            "rollback_reason": self.rollback_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        status = "ROLLED BACK" if self.rolled_back else "ACTIVE"
        return f"<ArchitectureSession {self.id}: {self.operation_type} ({status})>"
