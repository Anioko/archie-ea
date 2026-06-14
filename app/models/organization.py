"""
Organization model — tenant boundary for multi-tenancy.

Every piece of business data belongs to exactly one organization.
System-wide config (roles, permissions, feature flags, templates) is shared.
"""

from app import db


class Organization(db.Model):  # migration-exempt
    """Tenant boundary. Every piece of business data belongs to exactly one org."""

    __tablename__ = "organizations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    plan = db.Column(db.String(50), default="free")  # free, pro, enterprise
    is_active = db.Column(db.Boolean, default=True)
    settings = db.Column(db.JSON, default=dict)  # org-level config overrides
    max_users = db.Column(db.Integer, default=10)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    users = db.relationship("User", backref="organization", lazy="dynamic")

    def __repr__(self):
        return f"<Organization '{self.name}' ({self.slug})>"
