"""application_owners' first production write path: the Owners section on the
application record adds and removes a person per role, through the existing
organisation-scoped user list and a recorded primary-owner/admin permission
rule, with the model behind the standard tenant fence.

Users are built inline as in tests/test_arb_ea_tenant_isolation.py:24-37
(plain ``User(...)`` + ``db_session.add``/``flush``), with one addition: a
few routes exercised here (``application_edit``) are gated by
``require_roles("admin", "architect")``, a different check from this
feature's own ``is_org_admin`` / primary-owner rule, so every user here also
carries the "Administrator" RBAC role -- the same construction
tests/test_admin_org_member_idor.py:92-118 uses for the same reason. Setting
it universally does not weaken the ``is_org_admin`` / primary-owner
assertions below: they exercise a second, independent permission check this
task adds, not the RBAC role.

This module builds up across three commits, matching decisions A, then B/C/E,
then D; this first commit carries the model's own tenancy proof.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _make_user(db_session, org, *, is_org_admin=False, label="user"):
    from app.models.user import Role, User

    admin_role = Role.query.filter_by(name="Administrator").first()
    if admin_role is None:
        Role.insert_roles()
        admin_role = Role.query.filter_by(name="Administrator").first()

    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"owners-{label}-{suffix}@example.com",
        first_name="Owners",
        last_name=label,
        organization_id=org.id,
        role=admin_role,
        is_org_admin=is_org_admin,
        confirmed=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_app(db_session, org, name="Owners Target", **extra):
    from app.models.application_portfolio import ApplicationComponent

    row = ApplicationComponent(
        name=f"{name} {uuid.uuid4().hex[:6]}",
        organization_id=org.id,
        **extra,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _make_owner_row(db_session, app_row, user, ownership_type, **extra):
    from app.models.application_owner import ApplicationOwner

    row = ApplicationOwner(
        application_id=app_row.id,
        user_id=user.id,
        organization_id=app_row.organization_id,
        ownership_type=ownership_type,
        **extra,
    )
    db_session.add(row)
    db_session.flush()
    return row


# ─────────────────────────────────────────────────────── decision A: the model


def test_model_is_tenant_mixin_with_no_explicit_org_column():
    from app.models.application_owner import ApplicationOwner
    from app.models.mixins import TenantMixin

    assert issubclass(ApplicationOwner, TenantMixin)
    # The mixin's declared_attr organization_id must be the only source of
    # the column -- no shadowing explicit db.Column left behind.
    assert "organization_id" in ApplicationOwner.__table__.columns


# ───────────────────────────────────────────────────── the tenant fence itself


def test_cross_tenant_select_returns_only_tenant_rows(db_session, make_org, tenant_ctx):
    from app.models.application_owner import ApplicationOwner

    org_a = make_org("select-a")
    org_b = make_org("select-b")
    user_a = _make_user(db_session, org_a, label="select-user-a")
    user_b = _make_user(db_session, org_b, label="select-user-b")
    app_a = _make_app(db_session, org_a)
    app_b = _make_app(db_session, org_b)
    row_a = _make_owner_row(db_session, app_a, user_a, "primary")
    row_b = _make_owner_row(db_session, app_b, user_b, "primary")
    db_session.commit()

    with tenant_ctx(org_a.id):
        visible = ApplicationOwner.query.all()
        visible_ids = {row.id for row in visible}

    assert row_a.id in visible_ids, "org A's own ownership row must be visible in its own context"
    assert row_b.id not in visible_ids, (
        "TENANT LEAK: org A's request returned org B's ApplicationOwner row"
    )
    assert all(row.organization_id == org_a.id for row in visible)
