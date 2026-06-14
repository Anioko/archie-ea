"""ADM Deliverable models — TOGAF standard deliverable checklists per ADM phase."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from app import db


class ADMDeliverable(db.Model):
    __tablename__ = "adm_deliverables"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    # A, B, C, D, E, F, G, H, Requirements
    phase = Column(String(32), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    # True = seed/template row; False = board-specific instance
    is_template = Column(Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "phase": self.phase,
            "name": self.name,
            "description": self.description,
            "is_template": self.is_template,
        }


class ADMDeliverableCheck(db.Model):
    __tablename__ = "adm_deliverable_checks"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    deliverable_id = Column(Integer, ForeignKey("adm_deliverables.id"), nullable=False)
    board_id = Column(Integer, nullable=True)
    solution_id = Column(Integer, nullable=True)
    checked = Column(Boolean, default=False)
    checked_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "deliverable_id": self.deliverable_id,
            "board_id": self.board_id,
            "solution_id": self.solution_id,
            "checked": self.checked,
            "checked_at": self.checked_at.isoformat() if self.checked_at else None,
        }
