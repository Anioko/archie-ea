"""
Representation Model - ArchiMate 3.2 Business Layer

Representation: A perceptible form of the information carried by a business object.

ArchiMate 3.2 Definition:
A representation represents a perceptible form of the information carried by a
business object. It is the physical or digital realization of business information.

Examples:
- Document (contract PDF, invoice, receipt)
- Image (product photo, diagram, chart)
- Video (training video, promotional content)
- Audio (customer call recording)
- Data file (CSV, JSON, XML)
- Physical document (printed report, signed contract)

Relationships:
- Representation realizes Meaning (the interpretation)
- Representation is associated with Business Object (the information)
- Representation is stored in Artifact (physical/digital storage)
"""
from datetime import datetime

from app import db


class Representation(db.Model):
    """
    ArchiMate 3.2 Representation - Business Layer

    Perceptible form of information carried by a business object.
    Links business information (meaning) to its physical/digital form (artifact).
    """

    __tablename__ = "representations"

    id = db.Column(db.Integer, primary_key=True)

    # Basic identification
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    # Representation characteristics
    representation_type = db.Column(db.String(50))  # document, image, video, audio, data, physical
    format = db.Column(db.String(100))  # PDF, JPEG, MP4, CSV, JSON, XML, etc.
    location = db.Column(db.String(500))  # File path, URL, physical location

    # File/digital properties
    size_bytes = db.Column(db.BigInteger)
    mime_type = db.Column(db.String(100))  # application/pdf, image/jpeg, video/mp4
    encoding = db.Column(db.String(50))  # UTF - 8, ASCII, Base64, etc.
    checksum = db.Column(db.String(128))  # SHA - 256 hash for integrity verification
    version = db.Column(db.String(50))  # Version number for versioned documents

    # Content metadata
    language = db.Column(db.String(10), default="en")  # ISO 639 - 1 language code
    is_confidential = db.Column(db.Boolean, default=False)
    classification = db.Column(db.String(50))  # public, internal, confidential, restricted

    # ArchiMate relationships
    represents_meaning_id = db.Column(db.Integer, db.ForeignKey("meanings.id"), nullable=True)
    stored_in_artifact_id = db.Column(db.Integer, db.ForeignKey("code_artifacts.id"), nullable=True)

    # ArchiMate integration
    archimate_element_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"))
    archimate_layer = db.Column(db.String(20), default="Business")
    architecture_id = db.Column(db.Integer, db.ForeignKey("architecture_models.id"))

    # Audit fields
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Relationships
    represents_meaning = db.relationship(
        "Meaning", foreign_keys=[represents_meaning_id], backref="representations"
    )
    stored_in_artifact = db.relationship(
        "CodeArtifact", foreign_keys=[stored_in_artifact_id], backref="stored_representations"
    )
    archimate_element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])
    architecture = db.relationship("ArchitectureModel", backref="representations")
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    def __repr__(self):
        return f"<Representation {self.name} ({self.format})>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "representation_type": self.representation_type,
            "format": self.format,
            "location": self.location,
            "size_bytes": self.size_bytes,
            "mime_type": self.mime_type,
            "language": self.language,
            "is_confidential": self.is_confidential,
            "classification": self.classification,
            "archimate_element_id": self.archimate_element_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @property
    def human_readable_size(self):
        """Return file size in human-readable format"""
        if not self.size_bytes:
            return None

        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(self.size_bytes)
        unit_index = 0

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        return f"{size:.2f} {units[unit_index]}"

    @property
    def is_digital(self):
        """Check if this is a digital representation (vs physical)"""
        digital_types = ["document", "image", "video", "audio", "data"]
        return self.representation_type in digital_types

    def validate_integrity(self, actual_checksum):
        """Validate file integrity using checksum"""
        if not self.checksum:
            return None  # No checksum stored
        return self.checksum == actual_checksum


# Association table: Representation ↔ Business Object (many-to-many)
representation_business_objects = db.Table(
    "representation_business_objects",
    db.Column(
        "representation_id",
        db.Integer,
        db.ForeignKey("representations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "business_object_id",
        db.Integer,
        db.ForeignKey("business_objects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column("relationship_type", db.String(50)),  # realizes, associated_with
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
)
