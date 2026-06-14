"""
Import History Model

Tracks all import operations for rollback capability.
"""

from datetime import datetime
from app import db


class ImportHistory(db.Model):
    """
    History of import operations.

    Tracks what was imported and allows rollback.
    """

    __tablename__ = "import_history"

    id = db.Column(db.Integer, primary_key=True)

    # Import metadata
    filename = db.Column(db.String(255), nullable=False)
    import_type = db.Column(
        db.String(50), nullable=False
    )  # 'csv', 'excel', 'archimate'
    status = db.Column(
        db.String(20), default="completed"
    )  # 'completed', 'failed', 'rolled_back'

    # Who performed the import
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    user_email = db.Column(db.String(255), nullable=True)

    # When
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    rolled_back_at = db.Column(db.DateTime, nullable=True)

    # Results
    records_imported = db.Column(db.Integer, default=0)
    records_failed = db.Column(db.Integer, default=0)
    errors = db.Column(db.JSON, nullable=True)

    # Rollback tracking
    is_rolled_back = db.Column(db.Boolean, default=False)
    rolled_back_by = db.Column(db.Integer, nullable=True)
    rollback_reason = db.Column(db.Text, nullable=True)

    # Tracked entity IDs (for rollback)
    # Stores IDs of created records: {'applications': [1, 2, 3], 'vendors': [5, 6]}
    created_entity_ids = db.Column(db.JSON, default=dict)

    def __repr__(self):
        return f"<ImportHistory {self.id}: {self.filename} ({self.status})>"

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "filename": self.filename,
            "import_type": self.import_type,
            "status": self.status,
            "user_id": self.user_id,
            "user_email": self.user_email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "records_imported": self.records_imported,
            "records_failed": self.records_failed,
            "is_rolled_back": self.is_rolled_back,
            "rolled_back_at": self.rolled_back_at.isoformat()
            if self.rolled_back_at
            else None,
            "rollback_reason": self.rollback_reason,
        }

    @classmethod
    def create(cls, filename, import_type, user_id=None, user_email=None):
        """Create a new import history record."""
        history = cls(
            filename=filename,
            import_type=import_type,
            user_id=user_id,
            user_email=user_email,
        )
        db.session.add(history)
        db.session.commit()
        return history

    @classmethod
    def get_recent(cls, limit=50, user_id=None):
        """Get recent imports."""
        query = cls.query.order_by(cls.created_at.desc())
        if user_id:
            query = query.filter_by(user_id=user_id)
        return query.limit(limit).all()

    @classmethod
    def get_by_id(cls, import_id):
        """Get import history by ID."""
        return cls.query.get(import_id)

    def mark_completed(
        self, records_imported=0, records_failed=0, errors=None, entity_ids=None
    ):
        """Mark import as completed."""
        self.status = "completed"
        self.completed_at = datetime.utcnow()
        self.records_imported = records_imported
        self.records_failed = records_failed
        self.errors = errors or []
        self.created_entity_ids = entity_ids or {}
        db.session.commit()

    def mark_failed(self, errors=None):
        """Mark import as failed."""
        self.status = "failed"
        self.completed_at = datetime.utcnow()
        self.errors = errors or []
        db.session.commit()

    def mark_rolled_back(self, user_id, reason):
        """Mark import as rolled back."""
        self.is_rolled_back = True
        self.status = "rolled_back"
        self.rolled_back_at = datetime.utcnow()
        self.rolled_back_by = user_id
        self.rollback_reason = reason
        db.session.commit()

    def can_rollback(self):
        """Check if this import can be rolled back."""
        if self.is_rolled_back:
            return False, "Already rolled back"
        if self.status != "completed":
            return False, f"Import status is {self.status}, not completed"
        if not self.created_entity_ids:
            return False, "No entity IDs tracked for rollback"
        return True, "Can rollback"
