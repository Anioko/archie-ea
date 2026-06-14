"""
Reusable SQLAlchemy model mixins — canonical re-exports.

The actual implementations live in ``app/models/mixins.py`` (already used by
92+ model files).  This module re-exports them so that new code can import
from the ``app.core.database`` namespace::

    from app.core.database import TimestampMixin, SoftDeleteMixin

Canonical mixins:
- **TimestampMixin** — ``created_at``, ``updated_at``
- **SoftDeleteMixin** — ``is_active``, ``deleted_at``, ``deleted_by``,
  ``query_active()``, ``query_deleted()``
- **AuditMixin** — extends TimestampMixin + ``created_by``, ``updated_by``,
  ``version`` (optimistic locking)
- **HierarchyMixin** — ``parent_id``, ``level``, ``path`` (materialized path)
- **StatusMixin** — ``status``, ``status_changed_at``, ``previous_status``
"""

from app.models.mixins import (
    AuditMixin,
    HierarchyMixin,
    SoftDeleteMixin,
    StatusMixin,
    TimestampMixin,
)

__all__ = [
    "TimestampMixin",
    "SoftDeleteMixin",
    "AuditMixin",
    "HierarchyMixin",
    "StatusMixin",
]
