"""
Shared model re-exports for cross-module use.

Usage::

    from app.shared.models import BaseModel, AuditLog
    from app.shared.models import TimestampMixin, SoftDeleteMixin, AuditMixin
"""

from app.shared.models.audit import AuditLog
from app.shared.models.base import (
    AuditMixin,
    BaseModel,
    BaseRepository,
    HierarchyMixin,
    SoftDeleteMixin,
    StatusMixin,
    TimestampMixin,
)

__all__ = [
    "BaseModel",
    "BaseRepository",
    "TimestampMixin",
    "SoftDeleteMixin",
    "AuditMixin",
    "HierarchyMixin",
    "StatusMixin",
    "AuditLog",
]
