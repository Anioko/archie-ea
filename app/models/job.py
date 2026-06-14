from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import relationship

from app import db


class JobStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REQUIRES_REVIEW = "requires_review"


class Job(db.Model):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    task = Column(String(128), nullable=False)
    payload = Column(SQLiteJSON, nullable=True)
    status = Column(String(32), default=JobStatus.PENDING.value)
    result = Column(SQLiteJSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    def as_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "task": self.task,
            "payload": self.payload,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }
