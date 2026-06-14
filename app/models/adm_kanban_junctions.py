"""
ADM Kanban Junction Tables - Relational Models for Card Associations

Replaces JSON blob fields with proper relational models:
- CardApplication: Links cards to applications with relationship semantics
- CardSystem: Links cards to systems
- CardArchiMateElement: Links cards to ArchiMate elements with relationship types
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app import db


class CardApplicationRelationship(str, Enum):
    """Relationship types between cards and applications."""

    AFFECTS = "affects"  # Card changes/modifies the application
    IMPLEMENTS = "implements"  # Card implements the application
    DEPENDS_ON = "depends_on"  # Card depends on the application
    RETIRES = "retires"  # Card retires the application
    INTEGRATES_WITH = "integrates_with"  # Card creates integration
    MIGRATES = "migrates"  # Card migrates the application


class CardApplication(db.Model):
    """
    Junction table linking Kanban cards to Applications with relationship semantics.

    Replaces the application_ids JSON blob with proper referential integrity.
    """

    __tablename__ = "card_applications"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)

    # Foreign keys
    card_id = Column(Integer, ForeignKey("kanban_cards.id", ondelete="CASCADE"), nullable=False)
    application_id = Column(Integer, ForeignKey("application_components.id", ondelete="CASCADE"), nullable=False)

    # Relationship semantics
    relationship_type = Column(String(50), default="affects")  # From CardApplicationRelationship

    # Additional metadata
    impact_level = Column(String(20))  # critical, high, medium, low
    description = Column(Text)  # Specific description of how card affects application

    # Verification
    verified = Column(Boolean, default=False)
    verified_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    card = relationship("KanbanCard", backref="card_applications")
    application = relationship("ApplicationComponent", backref="kanban_card_applications")
    verified_by = relationship("User", foreign_keys=[verified_by_id], backref="verified_card_applications")
    created_by = relationship("User", foreign_keys=[created_by_id], backref="created_card_applications")

    def __repr__(self):
        return f"<CardApplication {self.card_id} -> {self.application_id}: {self.relationship_type}>"


class System(db.Model):
    """System entity — stub required for FK resolution in autogenerate."""

    __tablename__ = "systems"

    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    system_type = Column(String(50))
    description = Column(Text)


class CardSystem(db.Model):
    """
    Junction table linking Kanban cards to Systems.

    Replaces the system_ids JSON blob with proper referential integrity.
    """

    __tablename__ = "card_systems"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)

    # Foreign keys
    card_id = Column(Integer, ForeignKey("kanban_cards.id", ondelete="CASCADE"), nullable=False)
    system_id = Column(Integer, ForeignKey("systems.id", ondelete="CASCADE"), nullable=False)

    # Relationship metadata
    relationship_type = Column(String(50), default="affects")  # affects, implements, depends_on, integrates_with
    impact_level = Column(String(20))  # critical, high, medium, low
    description = Column(Text)

    # Verification
    verified = Column(Boolean, default=False)
    verified_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    card = relationship("KanbanCard", backref="card_systems")
    system = relationship("System", backref="kanban_cards")
    verified_by = relationship("User", foreign_keys=[verified_by_id], backref="verified_card_systems")
    created_by = relationship("User", foreign_keys=[created_by_id], backref="created_card_systems")

    def __repr__(self):
        return f"<CardSystem {self.card_id} -> {self.system_id}: {self.relationship_type}>"


class CardArchiMateRelationship(str, Enum):
    """Relationship types between cards and ArchiMate elements per ArchiMate 3.2."""

    # Structural relationships
    COMPOSITION = "composition"  # Whole consists of parts
    AGGREGATION = "aggregation"  # Whole groups objects
    ASSIGNMENT = "assignment"  # Responsibility for
    REALIZATION = "realization"  # Logical realized by physical

    # Dependency relationships
    SERVING = "serving"  # Provides to
    ACCESS = "access"  # Reads/writes
    INFLUENCE = "influence"  # Affects
    TRIGGERING = "triggering"  # Causes to start
    FLOW = "flow"  # Transfers something

    # Dynamic relationships
    SPECIALIZATION = "specialization"  # Is a type of

    # Other
    ASSOCIATION = "association"  # Unspecified


class CardArchiMateElement(db.Model):
    """
    Junction table linking Kanban cards to ArchiMate elements with relationship semantics.

    Replaces the archimate_elements JSON blob with proper referential integrity
    and ArchiMate 3.2-compliant relationship types.
    """

    __tablename__ = "card_archimate_elements"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)

    # Foreign keys
    card_id = Column(Integer, ForeignKey("kanban_cards.id", ondelete="CASCADE"), nullable=False)
    archimate_element_id = Column(Integer, ForeignKey("archimate_elements.id", ondelete="CASCADE"), nullable=False)

    # ArchiMate relationship semantics
    relationship_type = Column(String(50), default="association")  # From CardArchiMateRelationship
    relationship_direction = Column(String(20), default="source_to_target")  # source_to_target, bidirectional

    # Model layer context
    archimate_layer = Column(String(50))  # business, application, technology, motivation, implementation

    # Additional metadata
    description = Column(Text)  # How the card relates to this element
    properties = Column(JSON)  # Additional ArchiMate properties

    # Verification
    verified = Column(Boolean, default=False)
    verified_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    card = relationship("KanbanCard", backref="card_archimate_elements")
    archimate_element = relationship("ArchiMateElement", backref="kanban_cards")
    verified_by = relationship("User", foreign_keys=[verified_by_id], backref="verified_card_archimate_elements")
    created_by = relationship("User", foreign_keys=[created_by_id], backref="created_card_archimate_elements")

    def __repr__(self):
        return f"<CardArchiMateElement {self.card_id} -> {self.archimate_element_id}: {self.relationship_type}>"


class CardCapability(db.Model):
    """
    Junction table linking Kanban cards to Capabilities.

    Tracks which capabilities a card implements, affects, or depends on.
    """

    __tablename__ = "card_capabilities"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)

    # Foreign keys
    card_id = Column(Integer, ForeignKey("kanban_cards.id", ondelete="CASCADE"), nullable=False)
    capability_id = Column(Integer, ForeignKey("unified_capabilities.id", ondelete="CASCADE"), nullable=False)

    # Relationship semantics
    relationship_type = Column(String(50), default="implements")  # implements, affects, enables, depends_on
    impact_level = Column(String(20))  # critical, high, medium, low
    maturity_impact = Column(String(20))  # increases, decreases, maintains

    # Description
    description = Column(Text)

    # Verification
    verified = Column(Boolean, default=False)
    verified_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    card = relationship("KanbanCard", backref="card_capabilities")
    capability = relationship("UnifiedCapability", backref="kanban_cards")
    verified_by = relationship("User", foreign_keys=[verified_by_id], backref="verified_card_capabilities")
    created_by = relationship("User", foreign_keys=[created_by_id], backref="created_card_capabilities")

    def __repr__(self):
        return f"<CardCapability {self.card_id} -> {self.capability_id}: {self.relationship_type}>"


class BusinessInitiative(db.Model):
    """Business initiative — stub required for FK resolution in autogenerate."""

    __tablename__ = "business_initiatives"

    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    description = Column(Text)
    status = Column(String(50))


class CardInitiative(db.Model):
    """
    Junction table linking Kanban cards to Business Initiatives.

    Replaces the initiative_ids JSON blob.
    """

    __tablename__ = "card_initiatives"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)

    # Foreign keys
    card_id = Column(Integer, ForeignKey("kanban_cards.id", ondelete="CASCADE"), nullable=False)
    initiative_id = Column(Integer, ForeignKey("business_initiatives.id", ondelete="CASCADE"), nullable=False)

    # Relationship metadata
    contribution_type = Column(String(50), default="supports")  # supports, enables, delivers
    contribution_level = Column(String(20))  # primary, secondary, tertiary

    # Description
    description = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    card = relationship("KanbanCard", backref="card_initiatives")
    initiative = relationship("BusinessInitiative", backref="kanban_cards")

    def __repr__(self):
        return f"<CardInitiative {self.card_id} -> {self.initiative_id}: {self.contribution_type}>"


class CardDependency(db.Model):
    """
    Junction table for card-to-card dependencies.

    Replaces the depends_on and blocks JSON blobs with proper referential integrity.
    """

    __tablename__ = "card_dependencies"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)

    # Foreign keys - source card depends on target card
    source_card_id = Column(Integer, ForeignKey("kanban_cards.id", ondelete="CASCADE"), nullable=False)
    target_card_id = Column(Integer, ForeignKey("kanban_cards.id", ondelete="CASCADE"), nullable=False)

    # Dependency type
    dependency_type = Column(String(50), default="depends_on")  # depends_on, blocks, relates_to

    # Dependency characteristics
    is_blocking = Column(Boolean, default=True)  # True = blocks, False = relates
    is_critical = Column(Boolean, default=False)  # Critical path dependency

    # Status
    status = Column(String(50), default="active")  # active, resolved, waived

    # Description
    description = Column(Text)

    # Resolution tracking (if resolved/waived)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolution_notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    source_card = relationship("KanbanCard", foreign_keys=[source_card_id], backref="outgoing_dependencies")
    target_card = relationship("KanbanCard", foreign_keys=[target_card_id], backref="incoming_dependencies")
    resolved_by = relationship("User", foreign_keys=[resolved_by_id], backref="resolved_dependencies")
    created_by = relationship("User", foreign_keys=[created_by_id], backref="created_dependencies")

    def __repr__(self):
        return f"<CardDependency {self.source_card_id} {self.dependency_type} {self.target_card_id}>"
