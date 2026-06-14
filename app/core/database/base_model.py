"""
BaseModel — optional convenience base for new models.

Provides ``id``, ``created_at``, and ``updated_at`` out of the box so that
new modules don't have to redeclare boilerplate columns.

Usage::

    from app.core.database import BaseModel
    from app.extensions import db

    class Widget(BaseModel):
        __tablename__ = "widgets"
        name = db.Column(db.String(255), nullable=False)

Existing models that already inherit from ``db.Model`` are **not** required
to switch.  ``BaseModel`` is additive — it simply pre-defines common columns
so new code can be written with less repetition.
"""

from datetime import datetime

from app.extensions import db

from app.models.mixins import TimestampMixin


class BaseModel(TimestampMixin, db.Model):
    """Abstract base with ``id``, ``created_at``, ``updated_at``."""

    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True)

    def to_dict(self):
        """Generic serialiser — override in subclasses for custom logic."""
        result = {}
        for col in self.__table__.columns:
            value = getattr(self, col.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[col.name] = value
        return result

    def __repr__(self):
        return f"<{self.__class__.__name__} id={self.id}>"
