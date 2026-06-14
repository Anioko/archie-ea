"""
Account Service -- authentication and account management business logic.

Migrated from: app/account/views.py (inline logic extracted to service layer)
All behavior preserved exactly from the original views.py implementation.
"""
from flask import url_for
from flask_login import login_user, logout_user

try:
    from flask_rq import get_queue

    HAS_RQ = True
except ImportError:
    HAS_RQ = False
    get_queue = None

from app.extensions import db
from app.flask_email import send_email
from app.models import User


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
        """Log in a user via flask-login."""
        login_user(user, remember_me)

    @staticmethod
    def logout():
        """Log out the current user."""
        logout_user()

    @staticmethod
    def register_user(first_name, last_name, email, password):
        """Register a new user.

        Auto-confirms the account (email confirmation disabled).
        Admin can manage user access via /admin/users.

        Returns the newly created User object.
        """
        # Auto-assign to Default organization if none specified.
        # Without an org, multi-tenant tables (solutions, etc.) will reject inserts
        # with NOT NULL violation on organization_id.
        from app.models import Organization
        default_org = Organization.query.first()
        default_org_id = default_org.id if default_org else None

        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
            confirmed=True,  # Auto-confirm — email verification disabled for now
            organization_id=default_org_id,
        )
        db.session.add(user)
        db.session.commit()
        # Auto-login after registration
        login_user(user)
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
            return True, "Your password has been updated."
        return False, "The password reset link is invalid or has expired."

    @staticmethod
    def change_password(user, old_password, new_password):
        """Change a user's password after verifying the old one.

        Returns (success: bool, message: str).
        """
        if user.verify_password(old_password):
            user.password = new_password
            db.session.add(user)
            db.session.commit()
            return True, "Your password has been updated."
        return False, "Original password is invalid."

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
    def set_password(user, password):
        """Set a user's password (for join-from-invite flow)."""
        user.password = password
        db.session.add(user)
        db.session.commit()
