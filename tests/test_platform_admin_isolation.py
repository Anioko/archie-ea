"""F-01 regression: a tenant's platform admin must not reach other tenants.

The 2 Sep 2026 browser audit found a Northwind user with enterprise_role
"platform_admin" listing, editing, deactivating and deleting every organization
on the platform via /admin/organizations*. Root cause: those routes are (correctly)
gated on the SaaS super-admin boolean ``is_platform_admin``, but that flag had been
over-granted during provisioning to anyone holding the *tenant* platform_admin
role — including three real customer users with role "Architect".

Two things are pinned here so the conflation cannot come back:

1. ``enterprise_role == "platform_admin"`` alone must NOT imply ``is_platform_admin``
   at the model level (the role is per-tenant; the flag is cross-tenant).
2. A user with the tenant role but WITHOUT the flag gets 403 on every org-management
   route — list, detail, edit, toggle and delete — for an org that is not theirs.

Uses the HTTP-level authz pattern from tests/test_ba_tenant_and_authz.py (module
app with CSRF off, test_client, faked Flask-Login session + the g cache clear that
file documents). The negative cases are safe to run through test_client because
the decorator aborts before any full admin page renders.
"""

import pytest

from tests.test_ba_tenant_and_authz import (
    _cleanup_ids,
    _login,
    _make_org_id,
    _make_user_id,
)


@pytest.fixture(scope="module")
def app():
    from app import create_app, db

    app = create_app("testing")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        db.create_all()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def tenant_admin(app):
    """A tenant platform admin (role only, NO super-admin flag) in org A, plus a
    second org B they must not be able to touch. Yields ids, cleans up."""
    from app import db
    from app.models.organization import Organization
    from app.models.user import User

    with app.app_context():
        org_a = _make_org_id(db, "TenantA")
        org_b = _make_org_id(db, "TenantB")
        # Mirrors the audited shape exactly: tenant platform_admin role, Architect,
        # flag left at its default False.
        uid = _make_user_id(db, org_a, "TenantAdmin",
                            enterprise_role="platform_admin", role_name="Architect")
        yield {"user": uid, "org_a": org_a, "org_b": org_b}
        _cleanup_ids(db, User, [uid])
        _cleanup_ids(db, Organization, [org_a, org_b])


def test_tenant_role_does_not_imply_super_admin_flag(app):
    """The per-tenant role must never set the cross-tenant flag."""
    from app import db
    from app.models.user import User

    with app.app_context():
        org = _make_org_id(db, "Decouple")
        uid = _make_user_id(db, org, "Decouple", enterprise_role="platform_admin")
        try:
            user = db.session.get(User, uid)
            assert user.enterprise_role == "platform_admin"
            assert user.is_platform_admin is False, \
                "enterprise_role=platform_admin must not grant is_platform_admin"
        finally:
            _cleanup_ids(db, User, [uid])
            from app.models.organization import Organization
            _cleanup_ids(db, Organization, [org])


def test_tenant_admin_cannot_list_organizations(client, app, tenant_admin):
    with app.app_context():
        _login(client, tenant_admin["user"])
        r = client.get("/admin/organizations")
        assert r.status_code == 403


def test_tenant_admin_cannot_view_or_edit_another_org(client, app, tenant_admin):
    other = tenant_admin["org_b"]
    with app.app_context():
        _login(client, tenant_admin["user"])
        assert client.get(f"/admin/organizations/{other}").status_code == 403
        assert client.get(f"/admin/organizations/{other}/edit").status_code == 403


def test_tenant_admin_cannot_toggle_or_delete_another_org(client, app, tenant_admin):
    """The destructive routes are the dangerous half of F-01."""
    from app import db
    from app.models.organization import Organization

    other = tenant_admin["org_b"]
    with app.app_context():
        _login(client, tenant_admin["user"])
        assert client.post(f"/admin/organizations/{other}/toggle").status_code == 403
        assert client.post(f"/admin/organizations/{other}/delete").status_code == 403
        # and the org is still there — the 403 was real, not a redirect after acting
        assert db.session.get(Organization, other) is not None
