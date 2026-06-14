"""KanbanCardHistory — tracks column transitions for cycle time analytics."""
from datetime import datetime

from app import db


class KanbanCardHistory(db.Model):
    """Records each column transition for a KanbanCard."""

    __tablename__ = "kanban_card_history"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(
        db.Integer,
        db.ForeignKey("kanban_cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_column = db.Column(db.String(64), nullable=True)
    to_column = db.Column(db.String(64), nullable=False)
    transitioned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    transitioned_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    card = db.relationship(
        "KanbanCard",
        backref=db.backref("history", lazy="dynamic", cascade="all, delete-orphan"),
    )

    def __repr__(self) -> str:
        return (
            f"<KanbanCardHistory card={self.card_id} "
            f"{self.from_column!r} → {self.to_column!r}>"
        )
