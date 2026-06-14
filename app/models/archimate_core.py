from __future__ import annotations  # dead-code-ok

"""ArchiMate core models.

In normal app runtime, core ArchiMate models live in the monolithic
`app.models.models` module.

For lightweight contexts (notably Playwright E2E using `APP_FAST_INIT=1`), we
define a minimal subset of the ArchiMate core models here to avoid importing
the full monolithic model graph during startup.
"""

import os
from datetime import datetime  # dead-code-ok

from sqlalchemy.orm import relationship

from .. import db

_FAST_INIT = os.getenv("APP_FAST_INIT", "0") == "1"

if not _FAST_INIT:
    # Normal runtime: re-export models from models.py (already imported)
    from .models import ArchiMateElement, ArchiMateRelationship, ArchitectureModel

if _FAST_INIT:

    class ArchitectureModel(db.Model):
        __tablename__ = "architecture_models"
        __table_args__ = {"extend_existing": True}

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(100), nullable=False)
        version = db.Column(db.String(20))
        model_data = db.Column(db.Text)
        is_default = db.Column(db.Boolean, default=False, nullable=True)
        # Solution scoping (for journey-created architectures)
        solution_id = db.Column(
            db.Integer,
            db.ForeignKey("solutions.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        )

        def __repr__(self):
            return f"<ArchitectureModel {self.name} v{self.version}>"

    class ArchiMateElement(db.Model):
        __tablename__ = "archimate_elements"
        __table_args__ = {"extend_existing": True}

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(100), nullable=False)
        type = db.Column(db.String(50), index=True)
        layer = db.Column(db.String(30), index=True)
        description = db.Column(db.Text, nullable=True)

        # Scope for Enterprise vs Application level filtering
        # Values: 'enterprise', 'application', 'cross-cutting'
        scope = db.Column(db.String(30), nullable=True, default="enterprise", index=True)

        # TOGAF Building Block classification (Section 37)
        # Values: 'ABB' (Architecture Building Block), 'SBB' (Solution Building Block), or None
        building_block_type = db.Column(db.String(10), nullable=True, index=True)

        # TOGAF Plateau classification for transition architectures
        # Values: 'Baseline', 'Target', 'Transition', or None
        plateau = db.Column(db.String(20), nullable=True, index=True)

        # Custom tagged-value properties (CMP-043)
        custom_properties = db.Column(db.JSON, nullable=True, default=dict)

        parent_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True)
        # Keep as a plain integer in fast-init to avoid pulling in unrelated FK tables.
        architecture_id = db.Column(db.Integer, nullable=True)

        # ACM Domain-Driven Architecture metadata
        acm_domain = db.Column(db.String(10), nullable=True, index=True)
        is_baseline = db.Column(db.Boolean, default=False)
        acm_source = db.Column(db.String(20), nullable=True)
        overlay_code = db.Column(db.String(32), nullable=True)
        acm_properties = db.Column(db.JSON, default=dict)

        # Relationships
        # Note: app_component relationship is handled in the main ArchiMateElement model
        # to avoid conflicts with the duplicate class definition

        @classmethod
        def get_building_blocks(cls, block_type):
            """Filter elements by building block type (ABB or SBB)."""
            return cls.query.filter_by(building_block_type=block_type)

        @classmethod
        def get_by_plateau(cls, plateau_name):
            """Filter elements by plateau (Baseline, Target, Transition)."""
            return cls.query.filter_by(plateau=plateau_name)

        def __repr__(self):
            return f"<ArchiMateElement {self.name} ({self.type})>"

    class ArchiMateRelationship(db.Model):
        __tablename__ = "archimate_relationships"
        __table_args__ = {"extend_existing": True}

        id = db.Column(db.Integer, primary_key=True)
        type = db.Column(db.String(30), index=True)
        architecture_id = db.Column(db.Integer, nullable=True)
        source_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"), index=True)
        target_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"), index=True)

        # BUG-CMP-002: Relationship metadata — persists properties across diagrams
        description = db.Column(db.Text, nullable=True)
        access_mode = db.Column(db.String(20), nullable=True)  # read, write, readwrite (for access relationships)
        flow_label = db.Column(db.String(200), nullable=True)  # label for flow relationships
        custom_label = db.Column(db.String(200), nullable=True)  # user-defined label on any relationship
        created_by_id = db.Column(db.Integer, nullable=True)  # FK to users, kept as plain int to avoid circular imports
        created_at = db.Column(db.DateTime, nullable=True, default=db.func.now())
        updated_at = db.Column(db.DateTime, nullable=True, default=db.func.now(), onupdate=db.func.now())

        # GAP-INT-001: Structured connection specification for integration relationships
        # Stores per-relationship interface contract: data name, transfer strategy,
        # interface type, IAM method, file format, file name pattern, protocol, direction.
        connection_spec = db.Column(db.JSON, nullable=True, default=dict)

        def __repr__(self):
            return f"<ArchiMateRelationship {self.source_id} -> {self.target_id}>"


# -----------------------------------------------------------------------
# RelationshipSuggestion — always available (not gated by _FAST_INIT)
# -----------------------------------------------------------------------

class RelationshipSuggestion(db.Model):  # migration-exempt — uses db.create_all()
    """AI-suggested relationship awaiting EA review (BPP-006)."""

    __tablename__ = "relationship_suggestions"
    __table_args__ = (
        db.UniqueConstraint(
            "source_element_id", "target_element_id", "relationship_type",
            name="uq_rel_suggestion_triple",
        ),
        {"extend_existing": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    source_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=False, index=True
    )
    target_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=False, index=True
    )
    relationship_type = db.Column(db.String(30), nullable=False)
    confidence = db.Column(db.Float, nullable=False, default=0.5)
    source_method = db.Column(
        db.String(50), nullable=False, default="llm_semantic"
    )  # llm_semantic, transitive_inference, co_occurrence, abacus_import
    status = db.Column(
        db.String(20), nullable=False, default="pending", index=True
    )  # pending, accepted, rejected
    reason = db.Column(db.Text, nullable=True)
    reviewed_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True
    )
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now()
    )

    def __repr__(self):
        return (
            f"<RelationshipSuggestion {self.source_element_id}"
            f" -{self.relationship_type}-> {self.target_element_id}"
            f" ({self.status}, {self.confidence:.0%})>"
        )


# ArchiMate 3.2 relationship validity matrix
# Key: (relationship_type, source_layer, target_layer) → bool
# Layers: business, application, technology, motivation, strategy, implementation, physical
VALID_RELATIONSHIPS = {
    # Composition — within same layer only
    ("composition", "business", "business"): True,
    ("composition", "application", "application"): True,
    ("composition", "technology", "technology"): True,
    ("composition", "motivation", "motivation"): True,
    ("composition", "strategy", "strategy"): True,
    ("composition", "physical", "physical"): True,
    ("composition", "implementation", "implementation"): True,  # Deliverable → WorkPackage
    # Aggregation — within same layer only
    ("aggregation", "business", "business"): True,
    ("aggregation", "application", "application"): True,
    ("aggregation", "technology", "technology"): True,
    ("aggregation", "motivation", "motivation"): True,
    # Assignment — within same layer and specific cross-layer
    ("assignment", "business", "business"): True,
    ("assignment", "application", "application"): True,
    ("assignment", "technology", "technology"): True,
    ("assignment", "technology", "application"): True,
    # Realization — typically lower layer realizes upper layer
    ("realization", "business", "business"): True,
    ("realization", "application", "business"): True,
    ("realization", "technology", "application"): True,
    ("realization", "technology", "technology"): True,
    ("realization", "application", "application"): True,
    ("realization", "implementation", "motivation"): True,
    ("realization", "motivation", "motivation"): True,  # Goal → Outcome
    ("realization", "motivation", "strategy"): True,   # Goal → Capability
    ("realization", "strategy", "motivation"): True,   # CourseOfAction → Goal
    ("realization", "strategy", "business"): True,     # Capability → BusinessProcess/Service
    ("realization", "implementation", "implementation"): True,  # WorkPackage → Gap
    # Serving — cross-layer allowed
    ("serving", "application", "business"): True,
    ("serving", "application", "application"): True,
    ("serving", "technology", "application"): True,
    ("serving", "technology", "technology"): True,
    ("serving", "business", "business"): True,
    ("serving", "strategy", "strategy"): True,          # Capability serves ValueStream
    ("serving", "strategy", "motivation"): True,         # Capability serves Goal/Outcome
    # Access — within same layer and cross-layer (application accesses business objects)
    ("access", "business", "business"): True,
    ("access", "application", "application"): True,
    ("access", "application", "business"): True,
    ("access", "technology", "technology"): True,
    # Influence — motivation layer
    ("influence", "motivation", "motivation"): True,
    # Triggering — within same layer
    ("triggering", "business", "business"): True,
    ("triggering", "application", "application"): True,
    ("triggering", "technology", "technology"): True,
    ("triggering", "strategy", "strategy"): True,       # ValueStream stage → next stage (ordered)
    # Flow — within same layer
    ("flow", "business", "business"): True,
    ("flow", "application", "application"): True,
    ("flow", "technology", "technology"): True,
    # Association — any combination (most permissive)
    ("association", "business", "business"): True,
    ("association", "application", "application"): True,
    ("association", "technology", "technology"): True,
    ("association", "motivation", "motivation"): True,
    ("association", "motivation", "strategy"): True,   # Requirement → Capability
    ("association", "strategy", "strategy"): True,      # ValueStream ↔ Capability (uses), stage adjacency
    ("association", "strategy", "motivation"): True,    # Capability ↔ Goal/Outcome
    ("association", "implementation", "implementation"): True,  # WorkPackage → Plateau
    ("association", "business", "application"): True,
    ("association", "application", "business"): True,
    ("association", "application", "technology"): True,
    ("association", "technology", "application"): True,
    ("association", "business", "motivation"): True,
    ("association", "motivation", "business"): True,
    # Specialization — within same layer
    ("specialization", "business", "business"): True,
    ("specialization", "application", "application"): True,
    ("specialization", "technology", "technology"): True,
    ("specialization", "motivation", "motivation"): True,
    ("specialization", "strategy", "strategy"): True,
}

# Layer classification for element types
_ELEMENT_TYPE_LAYER = {
    "business_actor": "business", "business_role": "business",
    "business_collaboration": "business", "business_interface": "business",
    "business_process": "business", "business_function": "business",
    "business_interaction": "business", "business_event": "business",
    "business_service": "business", "business_object": "business",
    "contract": "business", "representation": "business", "product": "business",
    "application_component": "application", "application_collaboration": "application",
    "application_interface": "application", "application_function": "application",
    "application_interaction": "application", "application_process": "application",
    "application_event": "application", "application_service": "application",
    "data_object": "application",
    "node": "technology", "device": "technology", "system_software": "technology",
    "technology_collaboration": "technology", "technology_interface": "technology",
    "technology_function": "technology", "technology_process": "technology",
    "technology_interaction": "technology", "technology_event": "technology",
    "technology_service": "technology", "artifact": "technology",
    "communication_network": "technology", "path": "technology",
    "stakeholder": "motivation", "driver": "motivation", "assessment": "motivation",
    "goal": "motivation", "outcome": "motivation", "principle": "motivation",
    "requirement": "motivation", "constraint": "motivation",
    "meaning": "motivation", "value": "motivation",
    "resource": "strategy", "capability": "strategy", "course_of_action": "strategy",
    "value_stream": "strategy",
    "work_package": "implementation", "deliverable": "implementation",
    "implementation_event": "implementation", "plateau": "implementation", "gap": "implementation",
    "equipment": "physical", "facility": "physical",
    "distribution_network": "physical", "material": "physical",
}


def validate_relationship(rel_type, source_type, target_type):
    """Advisory validation of ArchiMate 3.2 relationship cardinality rules.

    Args:
        rel_type: Relationship type (e.g., 'composition', 'serving')
        source_type: Source element type (e.g., 'application_component')
        target_type: Target element type (e.g., 'business_service')

    Returns:
        Tuple of (is_valid: bool, message: str)
    """
    source_layer = _ELEMENT_TYPE_LAYER.get((source_type or "").lower(), "unknown")
    target_layer = _ELEMENT_TYPE_LAYER.get((target_type or "").lower(), "unknown")
    rel = (rel_type or "").lower()

    if source_layer == "unknown" or target_layer == "unknown":
        return True, "Element type not in registry; validation skipped"

    key = (rel, source_layer, target_layer)
    if key in VALID_RELATIONSHIPS:
        return True, f"Valid: {rel} from {source_layer} to {target_layer}"

    return False, (
        f"Invalid per ArchiMate 3.2: '{rel}' relationship from "
        f"{source_layer} layer ({source_type}) to {target_layer} layer ({target_type}) "
        f"is not in the validity matrix"
    )


# Extended ArchiMate 3.2 models
class CompositeStructure(db.Model):
    """Composite structures (ArchiMate 3.2 Other relationship)."""

    __tablename__ = "composite_structures"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    architecture_id = db.Column(db.Integer, nullable=True)
    parent_element_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"))
    child_element_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"))

    def __repr__(self):
        return f"<CompositeStructure {self.name}>"


class OtherRelationship(db.Model):
    """Other relationship type (ArchiMate 3.2)."""

    __tablename__ = "other_relationships"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    relationship_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    architecture_id = db.Column(db.Integer, nullable=True)
    source_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"))
    target_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"))

    def __repr__(self):
        return f"<OtherRelationship {self.relationship_type}>"


class SavedDiagram(db.Model):
    """Persisted composer diagram (viewpoint instance)."""

    __tablename__ = "saved_diagrams"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    viewpoint_type = db.Column(db.String(50), nullable=True)
    solution_id = db.Column(db.Integer, nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100), nullable=True)
    # QA-CMP-002: Optimistic locking — incremented on every save
    version = db.Column(db.Integer, default=1, server_default="1", nullable=False)

    positions = db.relationship(
        "SavedDiagramElement", backref="diagram",
        cascade="all, delete-orphan", lazy="dynamic",
    )
    rel_positions = db.relationship(
        "SavedDiagramRelationship", backref="diagram",
        cascade="all, delete-orphan", lazy="dynamic",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "viewpoint_type": self.viewpoint_type,
            "solution_id": self.solution_id,
            "description": self.description,
            "version": self.version or 1,
            "element_count": self.positions.count() if self.positions else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SavedDiagramElement(db.Model):
    """Element position within a saved diagram."""

    __tablename__ = "saved_diagram_elements"
    __table_args__ = (
        db.UniqueConstraint("diagram_id", "element_id", name="uq_diagram_element"),
        {"extend_existing": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    diagram_id = db.Column(db.Integer, db.ForeignKey("saved_diagrams.id"), nullable=False)
    element_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"), nullable=False)
    position_x = db.Column(db.Float, default=0)
    position_y = db.Column(db.Float, default=0)
    width = db.Column(db.Float, default=180)
    height = db.Column(db.Float, default=64)
    rendering_mode = db.Column(db.String(50), default="black_box")


class SavedDiagramRelationship(db.Model):
    """Relationship routing within a saved diagram."""

    __tablename__ = "saved_diagram_relationships"
    __table_args__ = (
        db.UniqueConstraint("diagram_id", "relationship_id", name="uq_diagram_rel"),
        {"extend_existing": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    diagram_id = db.Column(db.Integer, db.ForeignKey("saved_diagrams.id"), nullable=False)
    relationship_id = db.Column(db.Integer, db.ForeignKey("archimate_relationships.id"), nullable=False)
    waypoints_json = db.Column(db.Text, nullable=True)
    routing_style = db.Column(db.String(50), default="manhattan")
    is_architectural_intent = db.Column(db.Boolean, nullable=False, default=False)


__all__ = [
    "ArchitectureModel",
    "ArchiMateElement",
    "ArchiMateRelationship",
    "CompositeStructure",
    "OtherRelationship",
    "SavedDiagram",
    "SavedDiagramElement",
    "SavedDiagramRelationship",
    "VALID_RELATIONSHIPS",
    "validate_relationship",
]
