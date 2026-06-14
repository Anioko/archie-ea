from datetime import datetime

from .. import db


class CapabilitySet(db.Model):
    """Stores user-saved sets of capabilities for Architecture Assistant workflows.

    Fields:
    - id: primary key
    - user_id: FK to users.id (owner)
    - name: string
    - description: optional text
    - capability_ids: JSON list of capability IDs
    - is_public: bool, whether set is shared
    - created_at / updated_at
    """

    __tablename__ = "capability_sets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    capability_ids = db.Column(db.JSON, nullable=False)
    is_public = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", backref="capability_sets")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "capability_ids": self.capability_ids,
            "is_public": self.is_public,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
