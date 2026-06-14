"""
Core Model Mixins

Provides essential mixins for SQLAlchemy models including soft delete,
timestamps, auditing, hierarchy, and status management.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import backref, relationship


class TenantMixin:  # migration-exempt
    """Add to every model that holds tenant-specific business data.

    Provides an organization_id FK column and relationship. The SQLAlchemy
    event listener in app.middleware.tenant_isolation automatically filters
    SELECTs and auto-sets organization_id on INSERTs.
    """

    @declared_attr
    def organization_id(cls):
        from app import db
        return db.Column(
            db.Integer,
            db.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )

    @declared_attr
    def organization(cls):
        from app import db
        return db.relationship("Organization", lazy="select")


class OptimisticLockMixin:
    """Mixin for SQLAlchemy-enforced optimistic locking.

    Adds a version column that auto-increments on every UPDATE.
    SQLAlchemy raises StaleDataError if a concurrent session
    modified the row between read and write.
    """

    version = Column(Integer, default=1, nullable=False, server_default="1")

    @declared_attr
    def __mapper_args__(cls):
        return {"version_id_col": cls.__table__.c.version}


class SoftDeleteMixin:
    """Soft delete mixin for models."""

    deleted_at = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)

    def soft_delete(self):
        """Mark the record as deleted."""
        self.deleted_at = datetime.utcnow()
        self.is_deleted = True

    def restore(self):
        """Restore a soft-deleted record."""
        self.deleted_at = None
        self.is_deleted = False


class TimestampMixin:
    """Timestamp mixin for models."""

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AuditMixin:
    """Audit mixin for models."""

    created_by = Column(Integer, nullable=True)
    updated_by = Column(Integer, nullable=True)
    audit_notes = Column(Text, nullable=True)


class HierarchyMixin:
    """Hierarchy mixin for models with parent-child relationships."""

    parent_id = Column(Integer, nullable=True)
    level = Column(Integer, default=0, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)

    @declared_attr
    def children(cls):
        return relationship(cls, backref=backref("parent", remote_side=[cls.id]))


class StatusMixin:
    """Status mixin for models."""

    status = Column(String(50), default="active", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    def activate(self):
        """Set the model as active."""
        self.status = "active"
        self.is_active = True

    def deactivate(self):
        """Set the model as inactive."""
        self.status = "inactive"
        self.is_active = False


__all__ = ["OptimisticLockMixin", "SoftDeleteMixin", "TimestampMixin", "AuditMixin", "HierarchyMixin", "StatusMixin"]
