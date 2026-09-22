# migration-exempt
"""
Application Owner Model (NS-002)

Links users to applications they own for Application Manager persona filtering.
Part of North Star Persona MVP implementation.

ADR Reference: docs/adr/0011-application-manager-persona.md
"""

from datetime import datetime

from .. import db
from .mixins.core import TenantMixin


class ApplicationOwner(TenantMixin, db.Model):
    """
    Junction table linking users to applications they own.

    Supports multiple ownership types per application:
    - primary: Main accountable owner
    - backup: Secondary owner for coverage
    - technical: Technical/operations owner
    - business: Business/product owner

    Used by Application Manager persona to filter views to only owned apps.
    Tenant-fenced by TenantMixin: organization_id is stamped on insert and the
    ORM tenant-isolation listener scopes every select to the acting org.
    """
    __tablename__ = "application_owners"
    __table_args__ = (
        db.UniqueConstraint(
            "application_id", "user_id", "ownership_type",
            name="uq_application_owner_type"
        ),
        {"extend_existing": True},
    )

    id = db.Column(db.Integer, primary_key=True)

    # Foreign keys
    application_id = db.Column(
        db.Integer,
        db.ForeignKey("application_components.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Ownership details
    ownership_type = db.Column(
        db.String(50),
        nullable=False,
        default="primary",
    )  # 'primary', 'backup', 'technical', 'business'

    # Timestamps
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    application = db.relationship(
        "ApplicationComponent",
        backref=db.backref("owners", lazy="dynamic", cascade="all, delete-orphan"),
        foreign_keys=[application_id],
    )
    user = db.relationship(
        "User",
        backref=db.backref("owned_applications", lazy="dynamic"),
        foreign_keys=[user_id],
    )
    assigner = db.relationship(
        "User",
        foreign_keys=[assigned_by],
    )
    # TenantMixin supplies `organization_id` and an `organization` relationship
    # (no backref) — the explicit relationship this model used to declare had
    # its own backref, `Organization.application_owners`, which nothing read
    # (grep over app/ and tests/ confirms) and is dropped with it.

    # Valid ownership types
    OWNERSHIP_TYPES = ["primary", "backup", "technical", "business"]

    @property
    def is_primary(self):
        """True when this row records the main accountable owner.

        services.py has always read `ownership.is_primary` - in get_owned_apps'
        summary and in the ownership breakdown - but no such attribute existed, so
        both raised AttributeError and returned a 500 the moment a user actually
        owned something. An empty portfolio skipped the loop entirely, which is
        why the pages looked healthy until the first ownership row was created.
        """
        return self.ownership_type == "primary"

    def __repr__(self):
        return f"<ApplicationOwner app={self.application_id} user={self.user_id} type={self.ownership_type}>"

    def to_dict(self):
        return {
            "id": self.id,
            "application_id": self.application_id,
            "user_id": self.user_id,
            "ownership_type": self.ownership_type,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "assigned_by": self.assigned_by,
            "organization_id": self.organization_id,
        }

    @classmethod
    def get_owners_for_application(cls, application_id, organization_id):
        """Get all owners for an application.

        Tenancy is two layers, as in query_service.py: TenantMixin's listener
        already fences any select inside a request, and the explicit
        organization_id predicate below is defence in depth, keeping this
        method correct when called with no ambient request context (a job,
        a CLI command, a test looping tenants in one session).
        """
        return cls.query.filter(
            cls.application_id == application_id,
            cls.organization_id == organization_id,
        ).all()

    @classmethod
    def get_applications_for_user(cls, user_id, organization_id):
        """Get all application IDs owned by a user. Two-layer tenancy — see
        get_owners_for_application."""
        return [
            row.application_id
            for row in cls.query.filter(
                cls.user_id == user_id,
                cls.organization_id == organization_id,
            ).all()
        ]

    @classmethod
    def is_owner(cls, user_id, application_id, organization_id):
        """Check if user owns an application. Two-layer tenancy — see
        get_owners_for_application."""
        return cls.query.filter(
            cls.user_id == user_id,
            cls.application_id == application_id,
            cls.organization_id == organization_id,
        ).first() is not None
