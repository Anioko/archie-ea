"""
PendingInvitation — invitation a user must accept before role is granted (COM-007).

An existing user invited to another organisation gets a pending row here instead
of an immediate OrgRole. The row is removed on accept (OrgRole created) or
decline (nothing granted).
"""

from datetime import datetime

from app import db
from app.models.org_role import VALID_ORG_ROLES


class PendingInvitation(db.Model):  # migration-exempt
    """Stores an invitation for an existing user to join an organisation.

    The invitation must be accepted before the user gains any role or membership
    in the target organisation. Duplicate invitations for the same
    (organisation, user) pair are refused.
    """

    __tablename__ = "pending_invitations"
    __table_args__ = (
        db.UniqueConstraint(
            "organization_id", "user_id", name="uq_pending_invite_org_user"
        ),
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
    invited_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @classmethod
    def create_for(cls, org_id, user_id, role, invited_by_id=None):
        """Create a pending invitation. Returns (invitation, created: bool).

        If a pending invitation already exists for this org+user, returns the
        existing row and created=False.
        """
        if role not in VALID_ORG_ROLES:
            raise ValueError(
                f"Invalid role '{role}'. Must be one of {VALID_ORG_ROLES}"
            )
        existing = cls.query.filter_by(
            organization_id=org_id, user_id=user_id
        ).first()
        if existing is not None:
            return existing, False
        invitation = cls(
            organization_id=org_id,
            user_id=user_id,
            role=role,
            invited_by=invited_by_id,
        )
        db.session.add(invitation)
        db.session.flush()
        return invitation, True

    @classmethod
    def find_for_user(cls, user_id):
        """Return all pending invitations for a user."""
        return cls.query.filter_by(user_id=user_id).order_by(cls.created_at).all()

    @classmethod
    def find_one_or_none(cls, org_id, user_id):
        """Return the pending invitation for (org, user) or None."""
        return cls.query.filter_by(
            organization_id=org_id, user_id=user_id
        ).first()

    def __repr__(self):
        return (
            f"<PendingInvitation org={self.organization_id} "
            f"user={self.user_id} role={self.role}>"
        )