"""
SQLAlchemy Model Mixins

Reusable mixins for common model patterns:
- SoftDeleteMixin: Soft delete with is_active flag
- TimestampMixin: Created/updated timestamps
- AuditMixin: Full audit trail with user tracking

Usage:
    from app.models.mixins import SoftDeleteMixin, TimestampMixin

    class MyModel(db.Model, SoftDeleteMixin, TimestampMixin):
        __tablename__ = 'my_table'
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(255))
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, event
from sqlalchemy.ext.declarative import declared_attr

from app import db


class TimestampMixin:
    """
    Mixin for automatic created_at/updated_at timestamps.

    Adds:
        - created_at: Set on insert
        - updated_at: Set on insert and update
    """

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class SoftDeleteMixin:
    """
    Mixin for soft delete functionality.

    Adds:
        - is_active: Boolean flag (True = active, False = deleted)
        - deleted_at: Timestamp when soft deleted
        - deleted_by: User who performed the deletion

    Usage:
        # Soft delete
        record.soft_delete(deleted_by='admin@example.com')

        # Query active records only
        MyModel.query_active().all()

        # Restore
        record.restore()
    """

    is_active = Column(Boolean, default=True, nullable=False, index=True)

    deleted_at = Column(DateTime, nullable=True, index=True)

    deleted_by = Column(String(100), nullable=True)

    def soft_delete(self, deleted_by: str = None):
        """
        Soft delete this record.

        Args:
            deleted_by: Username/email of person performing deletion
        """
        self.is_active = False
        self.deleted_at = datetime.utcnow()
        self.deleted_by = deleted_by

    def restore(self):
        """Restore a soft-deleted record"""
        self.is_active = True
        self.deleted_at = None
        self.deleted_by = None

    @classmethod
    def query_active(cls):
        """
        Query only active (non-deleted) records.

        Returns:
            SQLAlchemy query filtered to is_active=True
        """
        return cls.query.filter_by(is_active=True)

    @classmethod
    def query_deleted(cls):
        """
        Query only soft-deleted records.

        Returns:
            SQLAlchemy query filtered to is_active=False
        """
        return cls.query.filter_by(is_active=False)

    @classmethod
    def query_all_including_deleted(cls):
        """
        Query all records including soft-deleted.

        Returns:
            Unfiltered SQLAlchemy query
        """
        return cls.query


class AuditMixin(TimestampMixin):
    """
    Full audit mixin with user tracking.

    Extends TimestampMixin with:
        - created_by: User who created the record
        - updated_by: User who last updated the record
        - version: Optimistic locking version number
    """

    created_by = Column(String(100), nullable=True)

    updated_by = Column(String(100), nullable=True)

    version = Column(Integer, default=1, nullable=False)

    def update_audit(self, updated_by: str = None):
        """
        Update audit fields manually.

        Call this when updating a record to track the user.

        Args:
            updated_by: Username/email of person performing update
        """
        self.updated_by = updated_by
        self.updated_at = datetime.utcnow()
        self.version += 1


class HierarchyMixin:
    """
    Mixin for hierarchical/tree structures.

    Adds:
        - parent_id: Self-referential foreign key
        - level: Depth in hierarchy (0 = root)
        - path: Materialized path for efficient queries (e.g., "1/5/23")

    Note: You must define the parent relationship in your model:

        parent = relationship('MyModel', remote_side=[id], backref='children')
    """

    @declared_attr
    def parent_id(cls):
        return Column(
            Integer,
            db.ForeignKey(f"{cls.__tablename__}.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        )

    level = Column(Integer, default=0, nullable=False, index=True)

    path = Column(String(1000), nullable=True, index=True)

    def update_path(self):
        """
        Update the materialized path based on parent.

        Call this after changing parent_id.
        """
        if self.parent_id is None:
            self.path = str(self.id)
            self.level = 0
        else:
            # Requires parent to be loaded
            if hasattr(self, "parent") and self.parent:
                self.path = f"{self.parent.path}/{self.id}"
                self.level = self.parent.level + 1

    def get_ancestors(self):
        """
        Get all ancestor IDs from the path.

        Returns:
            List of ancestor IDs (oldest first)
        """
        if not self.path:
            return []
        ids = self.path.split("/")
        return [int(id) for id in ids[:-1]]  # Exclude self

    def is_descendant_of(self, ancestor_id: int) -> bool:
        """
        Check if this node is a descendant of the given ancestor.

        Args:
            ancestor_id: ID of potential ancestor

        Returns:
            True if this node is a descendant
        """
        if not self.path:
            return False
        return f"/{ancestor_id}/" in f"/{self.path}/" or self.path.startswith(f"{ancestor_id}/")


class StatusMixin:
    """
    Mixin for status tracking with history.

    Adds:
        - status: Current status
        - status_changed_at: When status last changed
        - previous_status: What status was before current
    """

    status = Column(String(30), default="draft", nullable=False, index=True)

    status_changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    previous_status = Column(String(30), nullable=True)

    def change_status(self, new_status: str):
        """
        Change status with history tracking.

        Args:
            new_status: The new status value
        """
        if new_status != self.status:
            self.previous_status = self.status
            self.status = new_status
            self.status_changed_at = datetime.utcnow()


# =============================================================================
# Event Listeners for Mixins
# =============================================================================


def register_soft_delete_listener(model_class):
    """
    Register event listener to prevent hard deletes on soft-delete models.

    Usage:
        from app.models.mixins import register_soft_delete_listener

        class MyModel(db.Model, SoftDeleteMixin):
            ...

        register_soft_delete_listener(MyModel)
    """

    @event.listens_for(model_class, "before_delete")
    def prevent_hard_delete(mapper, connection, target):
        raise ValueError(
            f"Hard delete not allowed on {model_class.__name__}. "
            f"Use soft_delete() method instead."
        )


def register_hierarchy_path_listener(model_class):
    """
    Register event listener to auto-update hierarchy path.

    Usage:
        from app.models.mixins import register_hierarchy_path_listener

        class MyModel(db.Model, HierarchyMixin):
            ...

        register_hierarchy_path_listener(MyModel)
    """

    @event.listens_for(model_class, "before_insert")
    def set_initial_path(mapper, connection, target):
        if target.parent_id is not None:
            parent = model_class.query.get(target.parent_id)
            if parent and parent.path:
                target.path = f"{parent.path}/0"
                target.level = parent.level + 1
            else:
                target.path = "0"
                target.level = 0
        else:
            target.path = "0"
            target.level = 0

    @event.listens_for(model_class, "after_insert")
    def update_path_after_insert(mapper, connection, target):
        if target.path is None:
            target.update_path()
            # Update in database
            connection.execute(
                model_class.__table__.update()
                .where(model_class.id == target.id)
                .values(path=target.path, level=target.level)
            )
