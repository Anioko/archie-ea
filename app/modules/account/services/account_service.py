"""
Account Service -- authentication and account management business logic.

Migrated from: app/account/views.py (inline logic extracted to service layer)
All behavior preserved exactly from the original views.py implementation.
"""
import logging

from flask import session, url_for
from flask_login import logout_user

try:
    from flask_rq import get_queue

    HAS_RQ = True
except ImportError:
    HAS_RQ = False
    get_queue = None

from app.extensions import db
from app.flask_email import send_email
from app.models import User
from app.models.org_role import OrgRole
from app.services import session_registry

_log = logging.getLogger(__name__)


def _queue_email(*args, **kwargs):
    """Send email via queue if available, otherwise send synchronously."""
    if HAS_RQ and get_queue:
        get_queue().enqueue(send_email, *args, **kwargs)
    else:
        send_email(*args, **kwargs)


class AccountService:
    """Service layer for account-related operations."""

    @staticmethod
    def authenticate(email, password):
        """Authenticate a user by email and password.

        Returns the User object if credentials are valid, None otherwise.
        """
        user = User.find_by_email(email)
        if (
            user is not None
            and user.password_hash is not None
            and user.verify_password(password)
        ):
            return user
        return None

    @staticmethod
    def login(user, remember_me=False):
        """Log in a user via flask-login and mint a server-side session record."""
        session_registry.login_and_register(user, remember=remember_me)

    @staticmethod
    def logout():
        """Log out the current user, revoking their server-side session record.

        ``logout_user()`` always runs, even if the registry write fails: a DB
        blip revoking the server-side record must not turn a logout into a
        500 with the user still logged in client-side (low-priority item,
        round 2). The failure is still surfaced to the caller so it can be
        logged/reported rather than silently swallowed.
        """
        sid = session.get("_sid")
        try:
            session_registry.revoke(sid, "logout")
        except Exception:
            _log.error("account_service: failed to revoke session sid on logout", exc_info=True)
        finally:
            logout_user()

    @staticmethod
    def register_user(first_name, last_name, email, password):
        """Register a new user.

        Auto-confirms the account (email confirmation disabled).
        Admin can manage user access via /admin/users.

        Returns the newly created User object.
        """
        # Each self-serve sign-up gets its OWN organization (single-tenant isolation).
        # Team members are invited into an existing org rather than registering here.
        import re as _re
        import uuid as _uuid
        from app.models import Organization
        _label = ("{} {}".format(first_name or "", last_name or "").strip()
                  or (email.split("@")[0] if email else "New"))
        _base_slug = _re.sub(r"[^a-z0-9]+", "-",
                             ((first_name or "") + (last_name or "") or email.split("@")[0]).lower()).strip("-") or "org"
        _slug = _base_slug
        while Organization.query.filter_by(slug=_slug).first():
            _slug = "{}-{}".format(_base_slug, _uuid.uuid4().hex[:6])
        org = Organization(name="{}'s Workspace".format(_label), slug=_slug)
        db.session.add(org)
        db.session.flush()

        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
            confirmed=True,  # Auto-confirm — email verification disabled for now
            organization_id=org.id,
        )
        if hasattr(user, "is_org_admin"):
            user.is_org_admin = True
        db.session.add(user)
        try:
            db.session.flush()
            OrgRole.set_role(org.id, user.id, "org_admin", granted_by_id=user.id)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        # Auto-login after registration
        session_registry.login_and_register(user)
        # Email confirmation disabled — re-enable by removing confirmed=True above
        # and uncommenting the email block below:
        # token = user.generate_confirmation_token()
        # confirm_link = url_for("account.confirm", token=token, _external=True)
        # _queue_email(
        #     recipient=user.email,
        #     subject="Confirm Your Account",
        #     template="account/email/confirm",
        #     user=user,
        #     confirm_link=confirm_link,
        # )
        return user

    @staticmethod
    def request_password_reset(email):
        """Send a password reset email if the user exists."""
        user = User.find_by_email(email)
        if user:
            token = user.generate_password_reset_token()
            reset_link = url_for("account.reset_password", token=token, _external=True)
            _queue_email(
                recipient=user.email,
                subject="Reset Your Password",
                template="account/email/reset_password",
                user=user,
                reset_link=reset_link,
            )

    @staticmethod
    def reset_password(token, email, new_password):
        """Reset a user's password with the given token.

        Returns (success: bool, message: str).
        """
        user = User.find_by_email(email)
        if user is None:
            return False, "Invalid email address."
        if user.reset_password(token, new_password):
            # I've-lost-control-of-this-account path: kill everything,
            # including any session on the machine performing the reset.
            # There is no acting session to preserve -- a reset happens
            # while logged out.
            AccountService._revoke_other_sessions(user.id, "password_change", except_sid=None)
            return True, "Your password has been updated."
        return False, "The password reset link is invalid or has expired."

    @staticmethod
    def change_password(user, old_password, new_password):
        """Change a user's password after verifying the old one.

        Returns (success: bool, message: str, revoked_count: int | None).
        ``revoked_count`` is None when the password change itself failed, or
        when the change succeeded but session revocation could not be
        confirmed (caller must not report a fabricated count in that case).
        """
        if user.verify_password(old_password):
            user.password = new_password
            db.session.add(user)
            db.session.commit()
            # Keep the device the user is changing the password from signed
            # in -- only terminate every OTHER active session.
            revoked = AccountService._revoke_other_sessions(
                user.id, "password_change", except_sid=session.get("_sid")
            )
            return True, "Your password has been updated.", revoked
        return False, "Original password is invalid.", None

    @staticmethod
    def _revoke_other_sessions(user_id, reason, except_sid):
        """Revoke other active sessions for ``user_id``.

        Returns the number revoked, or ``None`` if revocation itself failed
        -- the password change has already committed at this point, so a
        revocation failure must never abort the request; it must also never
        be reported to the user as a specific count it cannot back up
        (fabricated-data rule).
        """
        try:
            count = session_registry.revoke_all_for_user(user_id, reason, except_sid=except_sid)
            # Audited unconditionally, including count == 0 (D5, round 2):
            # "password changed, zero other sessions to revoke" is itself
            # evidence a revocation check ran, and skipping the audit row
            # when count is 0 left no trace that it ever happened.
            from app.services import auth_audit

            user = User.query.get(user_id)  # tenant-scoping-ok: own-account post-auth lookup by primary key
            auth_audit.record_sessions_revoked(user, reason, count)
            return count
        except Exception:
            _log.error(
                "account_service: failed to revoke other sessions for user_id=%s reason=%s",
                user_id, reason, exc_info=True,
            )
            return None

    @staticmethod
    def request_email_change(user, new_email, password):
        """Request an email change after verifying the password.

        Returns (success: bool, message: str).
        """
        if user.verify_password(password):
            token = user.generate_email_change_token(new_email)
            change_email_link = url_for("account.change_email", token=token, _external=True)
            _queue_email(
                recipient=new_email,
                subject="Confirm Your New Email",
                template="account/email/change_email",
                user=user._get_current_object() if hasattr(user, '_get_current_object') else user,
                change_email_link=change_email_link,
            )
            return True, "A confirmation link has been sent to {}.".format(new_email)
        return False, "Invalid email or password."

    @staticmethod
    def confirm_email_change(user, token):
        """Confirm email change with the given token.

        Returns (success: bool, message: str).
        """
        if user.change_email(token):
            return True, "Your email address has been updated."
        return False, "The confirmation link is invalid or has expired."

    @staticmethod
    def send_confirmation_email(user):
        """Send (or re-send) account confirmation email."""
        actual_user = user._get_current_object() if hasattr(user, '_get_current_object') else user
        token = actual_user.generate_confirmation_token()
        confirm_link = url_for("account.confirm", token=token, _external=True)
        _queue_email(
            recipient=actual_user.email,
            subject="Confirm Your Account",
            template="account/email/confirm",
            user=actual_user,
            confirm_link=confirm_link,
        )

    @staticmethod
    def confirm_account(user, token):
        """Confirm a user's account with the given token.

        Returns (success: bool, message: str).
        """
        if user.confirm_account(token):
            return True, "Your account has been confirmed."
        return False, "The confirmation link is invalid or has expired."

    @staticmethod
    def join_from_invite(user_id, token):
        """Process a join-from-invite request.

        Returns (user, token_valid: bool, message: str).
        user is None if user_id not found.
        """
        # tenant-scoping-ok: pre-auth invite-join flow, no org context yet --
        # the signed confirmation token checked below is the real gate.
        new_user = User.query.get(user_id)
        if new_user is None:
            return None, False, "User not found."

        if new_user.password_hash is not None:
            return new_user, False, "You have already joined."

        if new_user.confirm_account(token):
            return new_user, True, "Account confirmed."
        else:
            # Re-send invite
            new_token = new_user.generate_confirmation_token()
            invite_link = url_for(
                "account.join_from_invite", user_id=user_id, token=new_token, _external=True
            )
            _queue_email(
                recipient=new_user.email,
                subject="You Are Invited To Join",
                template="account/email/invite",
                user=new_user,
                invite_link=invite_link,
            )
            return new_user, False, (
                "The confirmation link is invalid or has expired. Another "
                "invite email with a new link has been sent to you."
            )

    @staticmethod
    def accept_invitation(user, invitation_id):
        """Accept a pending invitation for the current user.

        Returns (success: bool, message: str). On success, creates the
        OrgRole row and removes the pending invitation.
        """
        from app.models.pending_invitation import PendingInvitation

        # tenant-scoping-ok: gated by user_id check below — only the
        # invitation owner can accept their own invitations.
        invitation = db.session.get(PendingInvitation, invitation_id)
        if invitation is None:
            return False, "Invitation not found."
        if invitation.user_id != user.id:
            return False, "This invitation is not for you."
        if invitation.is_expired():
            db.session.delete(invitation)
            db.session.commit()
            return False, "This invitation has expired. Ask an administrator to invite you again."
        OrgRole.set_role(
            invitation.organization_id,
            user.id,
            invitation.role,
            granted_by_id=invitation.invited_by,
        )
        db.session.delete(invitation)
        db.session.commit()
        return True, "Invitation accepted."

    @staticmethod
    def decline_invitation(user, invitation_id):
        """Decline a pending invitation for the current user.

        Returns (success: bool, message: str). On success, removes the
        pending invitation without granting any role.
        """
        from app.models.pending_invitation import PendingInvitation

        # tenant-scoping-ok: gated by user_id check below — only the
        # invitation owner can decline their own invitations.
        invitation = db.session.get(PendingInvitation, invitation_id)
        if invitation is None:
            return False, "Invitation not found."
        if invitation.user_id != user.id:
            return False, "This invitation is not for you."
        db.session.delete(invitation)
        db.session.commit()
        return True, "Invitation declined."

    @staticmethod
    def set_password(user, password):
        """Set a user's password (for join-from-invite flow)."""
        user.password = password
        db.session.add(user)
        db.session.commit()
        # Defensive: there should be no prior session for a fresh
        # join-from-invite user, but revoke everything just in case.
        AccountService._revoke_other_sessions(user.id, "password_change", except_sid=None)
