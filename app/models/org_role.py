"""
OrgRole — per-organisation role assignments for RBAC (COM-007).

One row per (organization, user) pair. Role hierarchy: org_admin > architect > viewer.
"""

from datetime import datetime

from app import db

VALID_ORG_ROLES = ("org_admin", "architect", "viewer")

ROLE_HIERARCHY = {
    "org_admin": 2,
    "architect": 1,
    "viewer": 0,
}


class OrgRole(db.Model):  # migration-exempt
    """Stores the role a user holds within a specific organisation."""

    __tablename__ = "org_roles"
    __table_args__ = (
        db.UniqueConstraint("organization_id", "user_id", name="uq_org_role_user"),
        {"extend_existing": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    role = db.Column(db.String(50), nullable=False, default="viewer")
    granted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @classmethod
    def get_role(cls, org_id, user_id):
        """Return the role string for user in org, or None if no row exists."""
        record = cls.query.filter_by(
            organization_id=org_id, user_id=user_id
        ).first()
        return record.role if record else None

    @classmethod
    def set_role(cls, org_id, user_id, role, granted_by_id=None):
        """Upsert the role for user in org. Caller must commit the session."""
        if role not in VALID_ORG_ROLES:
            raise ValueError(
                f"Invalid role '{role}'. Must be one of {VALID_ORG_ROLES}"
            )
        record = cls.query.filter_by(
            organization_id=org_id, user_id=user_id
        ).first()
        if record is None:
            record = cls(organization_id=org_id, user_id=user_id)
            db.session.add(record)
        record.role = role
        record.granted_by = granted_by_id
        db.session.flush()
        return record

    def __repr__(self):
        return (
            f"<OrgRole org={self.organization_id} "
            f"user={self.user_id} role={self.role}>"
        )
