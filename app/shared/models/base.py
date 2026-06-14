"""
Re-exports core database primitives for the shared namespace.

Canonical sources:
- BaseModel: app.core.database.base_model
- Mixins: app.core.database.mixins (-> app.models.mixins)
- BaseRepository: app.core.database.repository
"""

from app.core.database.base_model import BaseModel
from app.core.database.mixins import (
    AuditMixin,
    HierarchyMixin,
    SoftDeleteMixin,
    StatusMixin,
    TimestampMixin,
)
from app.core.database.repository import BaseRepository

__all__ = [
    "BaseModel",
    "BaseRepository",
    "TimestampMixin",
    "SoftDeleteMixin",
    "AuditMixin",
    "HierarchyMixin",
    "StatusMixin",
]
