from datetime import datetime

from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.orm import relationship

from app import db


class DashboardEdit(db.Model):
    __tablename__ = "dashboard_edits"
    id = db.Column(db.Integer, primary_key=True)
    table_name = db.Column(db.String(128), nullable=False, index=True)
    row_id = db.Column(db.String(128), nullable=False, index=True)
    data = db.Column(SQLITE_JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "table_name": self.table_name,
            "row_id": self.row_id,
            "data": self.data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def upsert(cls, table_name, row_id, data):
        instance = cls.query.filter_by(table_name=table_name, row_id=str(row_id)).first()
        if instance:
            instance.data = data
        else:
            instance = cls(table_name=table_name, row_id=str(row_id), data=data)
            db.session.add(instance)
        db.session.commit()
        return instance
