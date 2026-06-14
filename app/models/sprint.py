"""Sprint model for Technical Product Manager sprint planning."""
import enum
from datetime import datetime

from app import db


class SprintStatus(enum.Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    REVIEW = "review"
    CLOSED = "closed"


class Sprint(db.Model):
    __tablename__ = "sprints"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    board_id = db.Column(
        db.Integer,
        db.ForeignKey("kanban_boards.id", ondelete="CASCADE"),
        nullable=False,
    )
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    capacity_points = db.Column(db.Integer, default=0)
    status = db.Column(
        db.Enum(SprintStatus), default=SprintStatus.PLANNING, nullable=False
    )
    goal = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "board_id": self.board_id,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "capacity_points": self.capacity_points,
            "status": self.status.value,
            "goal": self.goal,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
