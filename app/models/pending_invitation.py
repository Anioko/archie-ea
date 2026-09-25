"""
PendingInvitation — invitation a user must accept before role is granted (COM-007).

An existing user invited to another organisation gets a pending row here instead
of an immediate OrgRole. The row is removed on accept (OrgRole created) or
decline (nothing granted).
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from app import db
from app.models.org_role import VALID_ORG_ROLES


def _utcnow():
    """Naive UTC, matching how the other timestamp columns are stored."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PendingInvitation(db.Model):  # migration-exempt
    """Stores an invitation for an existing user to join an organisation.

    The invitation must be accepted before the user gains any role or membership
    in the target organisation. Duplicate invitations for the same
    (organisation, user) pair are refused while the first is still valid. An
    invitation expires ``LIFETIME`` after it was created; an expired one can no
    longer be accepted, and inviting the same person again renews it.
    """

    LIFETIME = timedelta(days=14)

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
    created_at = db.Column(db.DateTime, default=_utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)

    @property
    def effective_expiry(self):
        """When this invitation stops being valid.

        Rows created before ``expires_at`` existed have no value; they expire
        ``LIFETIME`` after they were created.
        """
        if self.expires_at is not None:
            return self.expires_at
        return (self.created_at or _utcnow()) + self.LIFETIME

    def is_expired(self, now=None):
        return (now or _utcnow()) >= self.effective_expiry

    @classmethod
    def create_for(cls, org_id, user_id, role, invited_by_id=None):
        """Create a pending invitation. Returns (invitation, created: bool).

        If a valid pending invitation already exists for this org+user, returns
        the existing row and created=False. An expired one is renewed (new
        role, inviter and expiry) and returned with created=True. Two requests
        racing to create the same invitation are safe: the loser gets the
        winner's row and created=False instead of an error.
        """
        if role not in VALID_ORG_ROLES:
            raise ValueError(
                f"Invalid role '{role}'. Must be one of {VALID_ORG_ROLES}"
            )
        existing = cls.find_one_or_none(org_id, user_id)
        if existing is not None:
            if not existing.is_expired():
                return existing, False
            now = _utcnow()
            existing.role = role
            existing.invited_by = invited_by_id
            existing.created_at = now
            existing.expires_at = now + cls.LIFETIME
            db.session.flush()
            return existing, True
        invitation = cls(
            organization_id=org_id,
            user_id=user_id,
            role=role,
            invited_by=invited_by_id,
            expires_at=_utcnow() + cls.LIFETIME,
        )
        try:
            with db.session.begin_nested():
                db.session.add(invitation)
                db.session.flush()
        except IntegrityError:
            winner = cls.find_one_or_none(org_id, user_id)
            if winner is None:
                raise
            return winner, False
        return invitation, True

    @classmethod
    def find_for_user(cls, user_id):
        """Return the pending, unexpired invitations for a user."""
        rows = cls.query.filter_by(user_id=user_id).order_by(cls.created_at).all()
        return [row for row in rows if not row.is_expired()]

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
