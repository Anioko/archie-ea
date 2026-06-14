"""
Admin User Service - Business logic for admin user management.

Extracted from: app/admin/views.py (user CRUD, invitations, role changes)
"""
import logging
from typing import Optional, Tuple

from flask import url_for
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Role, User

try:
    from flask_rq import get_queue

    HAS_RQ = True
except ImportError:
    HAS_RQ = False
    get_queue = None

logger = logging.getLogger(__name__)


class AdminUserService:
    """Centralized business logic for admin user management."""

    @staticmethod
    def queue_email(*args, **kwargs) -> None:
        """Send email via queue if available, otherwise send synchronously."""
        from app.flask_email import send_email

        if HAS_RQ and get_queue:
            get_queue().enqueue(send_email, *args, **kwargs)
        else:
            send_email(*args, **kwargs)

    @staticmethod
    def get_all_users():
        """Get all registered users ordered by last name, first name."""
        return (
            User.query.options(joinedload(User.role))
            .order_by(
                func.lower(func.coalesce(User.last_name, "")),
                func.lower(func.coalesce(User.first_name, "")),
                User.id,
            )
            .all()
        )

    @staticmethod
    def get_all_roles():
        """Get all roles."""
        return Role.query.order_by(func.coalesce(Role.permissions, 0), Role.id).all()

    @staticmethod
    def get_user_or_404(user_id: int) -> User:
        """Get user by ID or abort with 404."""
        from flask import abort

        user = User.query.options(joinedload(User.role)).filter_by(id=user_id).first()
        if user is None:
            abort(404)
        return user

    @staticmethod
    def get_paginated_users(page: int = 1, per_page: int = 10, search_query: str = ""):
        """Get paginated users with optional search.

        Args:
            page: Page number.
            per_page: Items per page.
            search_query: Optional search string for name/email.

        Returns:
            Pagination object.
        """
        query = User.query.options(joinedload(User.role))
        if search_query:
            query = query.filter(
                User.first_name.ilike(f"%{search_query}%")
                | User.last_name.ilike(f"%{search_query}%")
                | User.email.ilike(f"%{search_query}%")
            )
        query = query.order_by(User.id.desc())
        return query.paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    def create_user(first_name: str, last_name: str, email: str,
                    password: str, role: Role) -> User:
        """Create a new user with a password.

        Args:
            first_name: User's first name.
            last_name: User's last name.
            email: User's email.
            password: Plain-text password.
            role: Role to assign.

        Returns:
            The newly created User.
        """
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
            confirmed=True,
            role=role,
        )
        db.session.add(user)
        db.session.commit()
        return user

    @staticmethod
    def invite_user(first_name: str, last_name: str, email: str,
                    role: Role) -> User:
        """Create a new user via invitation and send invite email.

        Args:
            first_name: User's first name.
            last_name: User's last name.
            email: User's email.
            role: Role to assign.

        Returns:
            The newly created User.
        """
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            role=role,
        )
        db.session.add(user)
        db.session.commit()

        token = user.generate_confirmation_token()
        invite_link = url_for(
            "account.join_from_invite", user_id=user.id, token=token, _external=True
        )
        AdminUserService.queue_email(
            recipient=user.email,
            subject="You Are Invited To Join",
            template="account/email/invite",
            user=user,
            invite_link=invite_link,
        )
        return user

    @staticmethod
    def change_user_email(user: User, new_email: str) -> None:
        """Change a user's email address (admin action, no confirmation needed).

        Args:
            user: User to modify.
            new_email: New email address.
        """
        user.email = new_email
        db.session.add(user)
        db.session.commit()

    @staticmethod
    def change_user_role(user: User, new_role: Role) -> None:
        """Change a user's role.

        Args:
            user: User to modify.
            new_role: New Role to assign.
        """
        user.role = new_role
        db.session.add(user)
        db.session.commit()

    @staticmethod
    def set_user_password(user: User, new_password: str, confirm_user: bool = True) -> None:
        """Set a user's password and optionally mark the account confirmed."""
        user.password = new_password
        if confirm_user:
            user.confirmed = True
        db.session.add(user)
        db.session.commit()

    @staticmethod
    def delete_user(user: User) -> Tuple[bool, str]:
        """Delete a user.

        Args:
            user: User to delete.

        Returns:
            Tuple of (success, message).
        """
        db.session.delete(user)
        db.session.commit()
        return True, "Successfully deleted user {}.".format(
            user.full_name()
        )
