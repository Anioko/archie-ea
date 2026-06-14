"""
ArchiMate 3.2 Structural Elements

Defines generic structural elements that apply across all layers:
- Grouping: Aggregates elements based on some common characteristic
- Junction: Connects relationships of the same type (AND, OR, XOR)
- Location: Models the location of elements (Physical is strictly Equipment/Facility, Location is generic)

These elements enable complex structural modeling and relationship logic.
"""

from datetime import datetime

from sqlalchemy import event

from .. import db

# Junction table for Grouping relationships (Many-to-Many)
# A Grouping can contain many ArchiMateElements
grouping_elements = db.Table(
    "grouping_elements",
    db.Column(
        "grouping_id",
        db.Integer,
        db.ForeignKey("structural_groupings.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "element_id",
        db.Integer,
        db.ForeignKey("archimate_elements.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Grouping(db.Model):
    """
    ArchiMate 3.2 Grouping Element

    The Grouping element aggregates or groups a composite of concepts that belong together
    based on some common characteristic.

    Examples:
    - "Financial Data Objects" (grouping of BusinessObjects)
    - "Purchase Processing" (grouping of ApplicationServices and BusinessProcesses)
    - "London Data Center" (grouping of Nodes and Devices - distinct from Location)
    """

    __tablename__ = "structural_groupings"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    # ArchiMate Linkage
    archimate_element_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"))

    # Grouping Specifics
    grouping_type = db.Column(db.String(50))  # Domain, Layer, Aspect, Project, Product, Dynamic
    criteria = db.Column(db.Text)  # Description of grouping criteria

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    archimate_element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])

    # Grouped Elements (Many-to-Many)
    elements = db.relationship(
        "ArchiMateElement",
        secondary=grouping_elements,
        backref=db.backref("groupings", lazy="dynamic"),
    )

    def __repr__(self):
        return f"<Grouping {self.name}>"


class Junction(db.Model):
    """
    ArchiMate 3.2 Junction Element

    A Junction is used to connect relationships of the same type.
    It corresponds to the 'And', 'Or', and 'Xor' logic gate concepts.

    Examples:
    - "Application A AND Application B" -> Serving -> "Business Process C"
    - "Outcome X OR Outcome Y" -> Realized By -> "Goal Z"
    """

    __tablename__ = "structural_junctions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(
        db.String(255), nullable=False, index=True
    )  # Usually "AND", "OR", "XOR" or descriptive

    # ArchiMate Linkage
    archimate_element_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"))

    # Junction Logic
    junction_type = db.Column(db.String(20), default="AND")  # AND, OR, XOR

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    archimate_element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])

    def __repr__(self):
        return f"<Junction {self.name} ({self.junction_type})>"


class Location(db.Model):
    """
    ArchiMate 3.2 Location Element

    A Location represents a conceptual or physical place or position where
    concepts are located (e.g., structure elements) or performed (e.g., behavior elements).

    Examples:
    - "Headquarters"
    - "London Branch"
    - "Cloud Region EU-West - 1"
    """

    __tablename__ = "structural_locations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    address = db.Column(db.Text)
    description = db.Column(db.Text)

    # ArchiMate Linkage
    archimate_element_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"))

    # Geospatial
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    altitude = db.Column(db.Float)

    # Classification
    location_type = db.Column(db.String(50))  # Physical, Virtual, Logical, Jurisdiction

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    archimate_element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])

    def __repr__(self):
        return f"<Location {self.name}>"


# ============================================================================
# SQLAlchemy Event Listeners
# ============================================================================


@event.listens_for(Grouping, "after_insert")
def create_grouping_archimate(mapper, connection, target):
    """Auto-create ArchiMateElement for Grouping"""
    from sqlalchemy import insert

    from .models import ArchiMateElement

    if not target.archimate_element_id:
        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="Grouping",
                layer="Reference",  # Grouping is strictly structural/composite
                description=target.description or f"Grouping: {target.name}",
            )
        )
        target.archimate_element_id = result.inserted_primary_key[0]


@event.listens_for(Junction, "after_insert")
def create_junction_archimate(mapper, connection, target):
    """Auto-create ArchiMateElement for Junction"""
    from sqlalchemy import insert

    from .models import ArchiMateElement

    if not target.archimate_element_id:
        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="Junction",
                layer="Reference",
                description=f"Junction ({target.junction_type})",
            )
        )
        target.archimate_element_id = result.inserted_primary_key[0]


@event.listens_for(Location, "after_insert")
def create_location_archimate(mapper, connection, target):
    """Auto-create ArchiMateElement for Location"""
    from sqlalchemy import insert

    from .models import ArchiMateElement

    if not target.archimate_element_id:
        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="Location",
                layer="Reference",  # Composite/Physical
                description=target.description or f"Location: {target.name}",
            )
        )
        target.archimate_element_id = result.inserted_primary_key[0]
