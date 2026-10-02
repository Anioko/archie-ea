"""
Core Model Mixins

Provides essential mixins for SQLAlchemy models including soft delete,
timestamps, auditing, hierarchy, and status management.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import backref, relationship


def _default_org_id():
    """Column default for tenant organization_id.

    Resolves the current request's organization (set by the tenant_context
    middleware on g.current_org_id) so inserts that bypass the tenant before_flush
    listener — raw Table.insert() in model events, seeders, bulk paths — still get
    an org rather than violating the NOT NULL constraint.

    Outside a request (CLI seeders, background jobs) there is no g.current_org_id.
    For a single-tenant install (exactly one Organization — the default for a
    self-hosted deployment) fall back to that org so `flask seed ...` and similar
    work out of the box. When several organizations exist we cannot safely guess
    the tenant, so we return None and let the NOT NULL constraint surface the
    missing context rather than silently writing into the wrong tenant.
    """
    try:
        from flask import g, has_request_context

        if has_request_context():
            return getattr(g, "current_org_id", None)
    except Exception:
        pass
    try:
        from app import db
        from app.models.organization import Organization

        with db.session.no_autoflush:
            ids = (
                db.session.query(Organization.id)
                .order_by(Organization.id.asc())
                .limit(2)
                .all()
            )
        if len(ids) == 1:
            return ids[0][0]
    except Exception:
        pass
    return None


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
            # Belt-and-suspenders: the tenant before_flush sets this for ORM inserts,
            # but raw Table.insert() (model events, seeders) bypasses it. This column
            # default fills the org from the request context for those paths too.
            default=_default_org_id,
        )

    @declared_attr
    def organization(cls):
        from app import db
        return db.relationship("Organization", lazy="select")


class HybridTenantMixin:  # migration-exempt
    """Add to a shared-catalogue model: platform-wide rows readable by every
    organisation, writable only by the platform, tailored through separate
    per-organisation override rows.

    Generalises the pattern first written as ``HybridCapabilityTenantMixin``
    in app/models/unified_capability.py (its own ``scope``/
    ``reference_capability_id`` columns and the ``do_orm_execute``/
    ``before_flush`` listeners at the bottom of that file -- kept distinct
    there for now, becomes a plain alias once that file's own event handlers
    are retired in favour of the generic ones installed by
    ``app/middleware/tenant_isolation.py``). Deliberately NOT ``TenantMixin``:
    that mixin's ``do_orm_execute`` equality filter would hide every shared
    row (``organization_id IS NULL``) from every organisation, which is the
    opposite of "shared".

    Nullable forever, not as an expand-step waiting for a later NOT NULL
    tightening: a shared catalogue row legitimately has no owning organisation.

    ``tenancy_scope``/``tailored_from_id`` are deliberately not named
    ``scope``/``reference_*_id`` (``UnifiedCapability``'s own names): several
    of the twelve classes mixing this in already declare their own unrelated
    ``scope`` or ``*_scope`` column (``EnterpriseArchitectureFramework.scope``
    is "enterprise, domain, application, technology", nothing to do with
    tenancy), and ``ReferenceModelCapability.reference_model_id`` already
    names a real, different foreign key. A name only this mixin uses avoids
    colliding with either.
    """

    @declared_attr
    def organization_id(cls):
        from app import db
        return db.Column(
            db.Integer,
            db.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        )

    @declared_attr
    def tenancy_scope(cls):
        """``"reference"`` (shared, ``organization_id IS NULL``, platform-
        writable only) or ``"tenant"`` (one organisation's own row, including
        a tailoring row -- see ``tailored_from_id``). Nullable until a row is
        classified: ``_protect_hybrid_tenant_writes`` (tenant_isolation.py)
        stamps ``"tenant"`` on any new row with ``organization_id`` set, the
        same way ``_protect_reference_capability_writes`` already does for
        ``UnifiedCapability``; a row the platform inserts directly with
        ``organization_id IS NULL`` must set ``tenancy_scope="reference"``
        itself to be treated as shared (an unclassified NULL-organisation row
        is not automatically shared -- the same rule
        ``UnifiedCapability.visibility_predicate`` documents).
        """
        from app import db
        return db.Column(db.String(16), nullable=True, index=True)

    @declared_attr
    def tailored_from_id(cls):
        """Set on a tenant's own row that overrides a shared reference row
        for that organisation only: the id of the reference row (on this
        same table) it tailors. NULL on an ordinary tenant-created row that
        tailors nothing and on every reference row itself.
        """
        from app import db
        return db.Column(
            db.Integer,
            db.ForeignKey(f"{cls.__tablename__}.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        )

    @classmethod
    def effective(cls, reference_id, organization_id):
        """The row an organisation actually sees for a given reference row:
        its own tailoring row if one exists, else the reference row itself.

        ``reference_id`` is always a reference row's own id -- a tenant row's
        id tailors nothing further (no second-level tailoring chain).

        No route calls this yet. Ten of the twelve classes mixing this in
        also declare their own globally-unique business key (a ``code`` or
        ``name`` column, unique across the whole table, not per
        organisation), so creating a tailoring row means the caller must
        already supply a value for that key distinct from the reference
        row's own -- this method does not generate or validate one. Until a
        route exists that handles that, this is read-only, correct plumbing
        with no caller.

        Callers must ensure their current tenant context matches the
        ``organization_id`` argument, or call this outside any tenant
        context; otherwise the fallback reference-row lookup
        (``cls.query.filter_by(id=reference_id).first()``) is subject to
        this same hybrid read filter and may be silently filtered out by a
        different organisation's own context, returning ``None`` for a
        reference row that genuinely exists.
        """
        from app import db

        if organization_id is not None:
            tailored = db.session.execute(
                db.select(cls).where(
                    cls.tailored_from_id == reference_id,
                    cls.organization_id == organization_id,
                )
            ).scalar_one_or_none()
            if tailored is not None:
                return tailored
        # .filter_by().first(), not .get(): the identity-map-bypass pitfall
        # this codebase avoids throughout (a cached cross-session object on a
        # .get() hit skips do_orm_execute); always issues real SQL.
        return cls.query.filter_by(id=reference_id).first()


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
