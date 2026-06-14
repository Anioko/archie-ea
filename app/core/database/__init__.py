"""
Core database package.

Provides base model classes, mixins, and repository pattern for all modules.

Usage::

    from app.core.database import BaseModel, TimestampMixin, SoftDeleteMixin
    from app.core.database.repository import BaseRepository
"""

from .base_model import BaseModel
from .mixins import (
    AuditMixin,
    HierarchyMixin,
    SoftDeleteMixin,
    StatusMixin,
    TimestampMixin,
)

__all__ = [
    "BaseModel",
    "TimestampMixin",
    "SoftDeleteMixin",
    "AuditMixin",
    "HierarchyMixin",
    "StatusMixin",
]
