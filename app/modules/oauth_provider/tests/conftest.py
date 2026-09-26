"""Reuse the shared fixtures from tests/conftest.py for this module's tests."""

from __future__ import annotations

from tests.conftest import (  # noqa: F401
    _schema,
    app,
    client,
    db_session,
    login_as,
    make_org,
    tenant_ctx,
)


def make_user(db_session, org, email):
    """One user-creation helper for every test module in this package,
    instead of each file hand-rolling its own copy."""
    from app.models.user import Role, User

    admin_role = Role.query.filter_by(name="Administrator").first()
    if admin_role is None:
        Role.insert_roles()
        admin_role = Role.query.filter_by(name="Administrator").first()

    user = User(
        email=email,
        first_name="Test",
        last_name="User",
        organization_id=org.id,
        role=admin_role,
        is_org_admin=True,
        confirmed=True,
    )
    user.password = "test"
    db_session.add(user)
    db_session.flush()
    return user