"""Business information model — the BIZBOK "information map".

BIZBOK's information map answers one question the capability map and the value
stream cannot: *what does the business run on*, and who touches it. Archie
already held most of the pieces and had never joined them:

* ``DataDomain`` (``app/models/process_data.py``) groups objects — Customer,
  Product, Finance.
* ``BusinessObject`` (``app/models/business_layer.py``) is the object itself,
  already tenant-scoped, already mirrored into the ArchiMate business layer,
  already carrying a definition, a steward, an owner and a classification.
* ``ProcessDataCrud`` (``app/models/relationship_tables.py``) records which
  *process* creates/reads/updates/deletes an object.
* ``DataObjectStorage`` (same file) records which *application* holds it.
* ``ArchiMateRelationship`` (``app/models/archimate_core.py``) carries
  object-to-object structure — an Order **composes** Order Lines, a Customer
  **associates** with an Order — between the two objects' ArchiMate elements.
  ArchiMate is the backbone, so the information map draws relationships there
  rather than in a private table that nothing else can read.

The one genuinely missing link is capability→object CRUD. BIZBOK's information
map is cross-mapped against the *capability* map, not the process model:
"Customer Management creates and updates Customer" is a statement about a
capability. ``ProcessDataCrud`` cannot stand in for it — a capability is not a
process, and most organisations model far fewer capabilities than processes.

Hence exactly one new table here.
"""

from datetime import datetime

from app.models.mixins import TenantMixin

from .. import db

# The CRUD letters, in the order they are always spoken.
CRUD_FLAGS = ("creates", "reads", "updates", "deletes")


class CapabilityObjectCrud(TenantMixin, db.Model):
    """CRUD matrix cell: one business capability against one business object.

    A row exists only where somebody has said something about the pair. An
    absent row means "not stated", which is why there is no "none of the four"
    default worth writing: a cell with all four flags false is a deliberate
    statement that the capability touches the object without CRUD (it consults
    a report, say), and the UI renders an em dash for the absent case rather
    than a fabricated "no access".
    """

    __tablename__ = "capability_object_crud"
    __table_args__ = (
        # Composite of two foreign keys to tenant-scoped rows: two
        # organisations cannot reach the same pair, so this cannot collide
        # across tenants.
        db.UniqueConstraint(
            "capability_id", "business_object_id", name="uq_capability_object_crud"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    capability_id = db.Column(
        db.Integer, db.ForeignKey("business_capability.id"), nullable=False, index=True
    )
    business_object_id = db.Column(
        db.Integer, db.ForeignKey("business_objects.id"), nullable=False, index=True
    )

    # CRUD
    creates = db.Column(db.Boolean, nullable=False, server_default=db.text("false"), default=False)
    reads = db.Column(db.Boolean, nullable=False, server_default=db.text("false"), default=False)
    updates = db.Column(db.Boolean, nullable=False, server_default=db.text("false"), default=False)
    deletes = db.Column(db.Boolean, nullable=False, server_default=db.text("false"), default=False)

    # Which capability is accountable for the object's definition and quality.
    # At most one per object is meaningful, but that is a data-quality question
    # the UI surfaces rather than a constraint the database can express without
    # a partial index that reconcile-schema could not add.
    is_owning_capability = db.Column(
        db.Boolean, nullable=False, server_default=db.text("false"), default=False
    )

    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    capability = db.relationship("BusinessCapability", backref="object_crud_operations")
    business_object = db.relationship("BusinessObject", backref="capability_crud_operations")

    @property
    def crud_letters(self):
        """"CRUD", "CR", "R" … or ``None`` when no operation is claimed.

        ``None`` rather than "None" or "" on purpose: the template renders it
        as an em dash, and a caller that prints the string gets a dash rather
        than a word that reads like a value.
        """
        letters = "".join(
            letter
            for letter, field in zip("CRUD", CRUD_FLAGS)
            if getattr(self, field, False)
        )
        return letters or None

    def __repr__(self):
        return (
            f"<CapabilityObjectCrud cap:{self.capability_id} "
            f"obj:{self.business_object_id} {self.crud_letters or '-'}>"
        )
