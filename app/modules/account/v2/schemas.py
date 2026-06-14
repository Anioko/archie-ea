"""
Validation schemas for account v2 endpoints.

Account endpoints primarily use WTForms for HTML form validation (preserved
from v1). These schemas provide additional API-level validation for any
future JSON API endpoints (e.g. programmatic login, registration API).

The WTForms classes in account_forms.py remain the canonical validators
for the HTML form-based endpoints.
"""

from app.core.validation.schemas import BoolField, Schema, StringField


class LoginSchema(Schema):
    """JSON login request validation (for future API login endpoint)."""
    email = StringField(
        required=True,
        min_length=1,
        max_length=64,
        pattern=r"^[^@]+@[^@]+\.[^@]+$",
        description="User email address",
    )
    password = StringField(
        required=True,
        min_length=1,
        max_length=128,
        description="User password",
    )
    remember_me = BoolField(
        required=False,
        default=False,
        description="Keep user logged in",
    )


class RegistrationSchema(Schema):
    """JSON registration request validation (for future API registration)."""
    first_name = StringField(
        required=True,
        min_length=1,
        max_length=64,
        description="User first name",
    )
    last_name = StringField(
        required=True,
        min_length=1,
        max_length=64,
        description="User last name",
    )
    email = StringField(
        required=True,
        min_length=1,
        max_length=64,
        pattern=r"^[^@]+@[^@]+\.[^@]+$",
        description="User email address",
    )
    password = StringField(
        required=True,
        min_length=6,
        max_length=128,
        description="User password",
    )


class ResetPasswordSchema(Schema):
    """JSON password reset request validation."""
    email = StringField(
        required=True,
        min_length=1,
        max_length=64,
        pattern=r"^[^@]+@[^@]+\.[^@]+$",
        description="User email address",
    )


class ChangePasswordSchema(Schema):
    """JSON change password request validation."""
    old_password = StringField(
        required=True,
        min_length=1,
        max_length=128,
        description="Current password",
    )
    new_password = StringField(
        required=True,
        min_length=6,
        max_length=128,
        description="New password",
    )


class ChangeEmailSchema(Schema):
    """JSON change email request validation."""
    email = StringField(
        required=True,
        min_length=1,
        max_length=64,
        pattern=r"^[^@]+@[^@]+\.[^@]+$",
        description="New email address",
    )
    password = StringField(
        required=True,
        min_length=1,
        max_length=128,
        description="Current password for verification",
    )
