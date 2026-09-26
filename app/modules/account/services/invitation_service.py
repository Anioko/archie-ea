"""
Invitations to join an organisation by e-mail.

A person with no account is invited by address: an account is opened for them
in the INVITER'S organisation, with no password, and a single-use link is
e-mailed to them. Following the link lets them set a password; only then is the
organisation role granted and the address counted as confirmed. The link is an
``AccountToken`` of purpose "invitation" bound to that organisation, so it can
put its holder nowhere else.

People who already have an account elsewhere keep the existing in-product
invitation (``PendingInvitation``) they accept after signing in.
"""
import logging

from flask import url_for

from app.extensions import db
from app.flask_email import deliver_email, mail_available
from app.models import User
from app.models.account_token import PURPOSE_INVITATION, AccountToken
from app.models.org_role import VALID_ORG_ROLES, OrgRole
from app.models.user import ROLE_PLATFORM_ADMIN, ROLE_SOLUTION_ARCHITECT, VALID_ROLES

_log = logging.getLogger(__name__)

MAIL_UNAVAILABLE = (
    "E-mail is not available on this server, so no invitation can be sent. "
    "Nothing was created."
)

# Personas an organisation administrator may give a teammate. Platform
# administration is not the organisation's to hand out.
INVITABLE_PERSONAS = [r for r in VALID_ROLES if r != ROLE_PLATFORM_ADMIN]


class InvitationError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def is_unactivated(user):
    """An account opened by an invitation that has not been taken up yet."""
    return (
        user.password_hash is None
        and not user.confirmed
        and not getattr(user, "external_id", None)
    )


def _send(token_row, raw, inviter, org_name):
    link = url_for("account.join", token=raw, _external=True)
    delivered, error = deliver_email(
        recipient=token_row.user.email,
        subject="You are invited to join {}".format(org_name),
        template="account/email/invite",
        user=token_row.user,
        invite_link=link,
        inviter=inviter,
        organisation_name=org_name,
        expires_at=token_row.expires_at,
    )
    token_row.record_delivery(delivered, error)
    return delivered, error


def organisation_name(org_id):
    from app.models.organization import Organization

    # org_id is the caller's own organisation, or the one a redeemed invitation is bound to.
    # tenant-scoping-ok: only that organisation's display name is read
    org = db.session.get(Organization, org_id)
    return org.name if org is not None else "your organisation"


def invite_new_person(org_id, inviter, email, org_role="viewer", persona=None,
                      first_name=None, last_name=None, platform_role=None):
    """Invite an address with no activated account into ``org_id``.

    Returns ``(token_row, delivered, error)``. Raises InvitationError when the
    invitation cannot be made; nothing is written in that case.
    """
    if org_role not in VALID_ORG_ROLES:
        raise InvitationError("Invalid role '{}'.".format(org_role))
    persona = persona or ROLE_SOLUTION_ARCHITECT
    if persona not in INVITABLE_PERSONAS:
        raise InvitationError("Invalid persona '{}'.".format(persona))
    if not mail_available():
        raise InvitationError(MAIL_UNAVAILABLE, status=503)

    user = User.find_by_email(email)
    if user is not None:
        if user.organization_id != org_id or not is_unactivated(user):
            raise InvitationError("This address already has an account.", status=409)
        # Tenant-filtered to the caller's organisation, and checked again.
        open_invite = (
            AccountToken.query.filter_by(
                user_id=user.id, purpose=PURPOSE_INVITATION, organization_id=org_id
            )
            .order_by(AccountToken.id.desc())
            .first()
        )
        if open_invite is not None and open_invite.is_usable():
            raise InvitationError(
                "An invitation for this address is still open. Use Resend to send it again.",
                status=409,
            )
        user.enterprise_role = persona
    else:
        user = User(
            first_name=first_name or None,
            last_name=last_name or None,
            email=email,
            organization_id=org_id,
            confirmed=False,
            enterprise_role=persona,
        )
        if platform_role is not None:
            user.role = platform_role
        db.session.add(user)
        db.session.flush()

    token_row, raw = AccountToken.issue(
        user, PURPOSE_INVITATION, organization_id=org_id,
        invited_by_id=inviter.id, role=org_role,
    )
    delivered, error = _send(token_row, raw, inviter, organisation_name(org_id))
    db.session.commit()
    return token_row, delivered, error


def invitations_for(org_id):
    """Invitations this organisation has sent that have not been taken up."""
    rows = (
        AccountToken.query.filter(
            AccountToken.organization_id == org_id,
            AccountToken.purpose == PURPOSE_INVITATION,
            AccountToken.used_at.is_(None),
            AccountToken.revoked_at.is_(None),
        )
        .order_by(AccountToken.created_at.desc())
        .all()
    )
    return [row for row in rows if row.user is not None and is_unactivated(row.user)]


def _invitation_in_org(org_id, token_id):
    row = db.session.get(AccountToken, token_id)
    if (
        row is None
        or row.organization_id != org_id
        or row.purpose != PURPOSE_INVITATION
        or row.used_at is not None
        or row.revoked_at is not None
    ):
        raise InvitationError("Invitation not found.", status=404)
    return row


def resend(org_id, inviter, token_id):
    """Send a fresh link for an invitation in ``org_id``; the old link stops working."""
    row = _invitation_in_org(org_id, token_id)
    if not mail_available():
        raise InvitationError(MAIL_UNAVAILABLE, status=503)
    new_row, raw = AccountToken.issue(
        row.user, PURPOSE_INVITATION, organization_id=org_id,
        invited_by_id=inviter.id, role=row.role,
    )
    delivered, error = _send(new_row, raw, inviter, organisation_name(org_id))
    db.session.commit()
    return new_row, delivered, error


def revoke(org_id, token_id):
    from app.models.account_token import _utcnow

    row = _invitation_in_org(org_id, token_id)
    row.revoked_at = _utcnow()
    db.session.commit()
    return row


def find_joinable(raw_token):
    """The invitation behind a link, or None when the link cannot be used."""
    row = AccountToken.find_usable(raw_token, PURPOSE_INVITATION)
    if row is None or row.user is None:
        return None
    if row.user.organization_id != row.organization_id or not is_unactivated(row.user):
        return None
    return row


def accept(raw_token, password):
    """Take up an invitation: set the password, confirm, grant the role.

    Returns the new member, or None when the link cannot be used (expired,
    already used, withdrawn, or not bound to the account's organisation).
    """
    if find_joinable(raw_token) is None:
        return None
    row = AccountToken.consume(raw_token, PURPOSE_INVITATION)
    if row is None:
        return None
    user = row.user
    if user.organization_id != row.organization_id:
        db.session.rollback()
        return None
    user.password = password
    user.confirmed = True
    OrgRole.set_role(
        row.organization_id, user.id, row.role or "viewer",
        granted_by_id=row.invited_by_id,
    )
    db.session.commit()
    _log.info("invitation %s taken up into organisation %s", row.id, row.organization_id)
    return user
