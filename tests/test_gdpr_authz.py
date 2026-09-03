"""Authorisation contract for the GDPR data-subject API (`gdpr_bp`).

Two things are pinned here, and the first is the reason the file exists.

1. **The blueprint is registered.** `gdpr_bp` shipped fully written but was
   never passed to `register_blueprint`, so a complete export/erasure
   capability was unreachable in production for its entire life. The
   `url_for` assertions below fail with `BuildError` the moment that
   regresses — a test that merely POSTed to a hard-coded path would 404 in
   exactly the same way whether the bug was back or the URL had simply moved.

2. **Self-or-platform-admin is actually enforced.** Export and status are
   readable by the data subject or a platform admin; erasure is
   platform-admin-only, deliberately including self-erasure.

Written against the shared fixtures in ``tests/conftest.py`` (``db_session``
rolls the whole test back, so the erasure test can anonymise a real row
without leaving residue in the shared database). ``login_as`` is used before
*every* request whose identity matters: ``db_session`` holds one app context
open for the test, flask_login caches the resolved user on ``g._login_user``,
and without clearing it the "attacker" request runs as the victim and reports
a pass that never happened.
"""

from __future__ import annotations

import uuid

import pytest
from flask import url_for


def _make_user(db_session, org, *, platform_admin: bool = False):
    from app.models.user import Permission, Role, User

    suffix = uuid.uuid4().hex[:12]
    user = User(
        # An app-wide before_request bounces unconfirmed users to
        # /account/unconfirmed, which would turn every assertion below into a
        # 302 that says nothing about authorisation.
        confirmed=True,
        email=f"gdpr-{suffix}@example.test",
        first_name="Data",
        last_name="Subject",
        organization_id=org.id,
        is_platform_admin=platform_admin,
        password_hash="scrypt:dummy",
        external_id=f"ext-{suffix}",
        sso_provider="oidc",
    )
    if platform_admin:
        user.role = Role.query.filter(
            Role.permissions.op("&")(Permission.ADMINISTER) == Permission.ADMINISTER
        ).first()
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# 1. The blueprint is registered and its endpoints resolve
# ---------------------------------------------------------------------------


def test_gdpr_endpoints_are_registered_and_build(app):
    with app.test_request_context("/"):
        assert url_for("gdpr_bp.export_user_data", user_id=1) == "/api/gdpr/export/1"
        assert url_for("gdpr_bp.delete_user_data", user_id=1) == "/api/gdpr/delete/1"
        assert url_for("gdpr_bp.gdpr_status", user_id=1) == "/api/gdpr/status/1"


# ---------------------------------------------------------------------------
# 2. Export / status — self or platform admin
# ---------------------------------------------------------------------------


def test_owner_can_export_own_data(db_session, make_org, client, login_as):
    org = make_org("gdpr-owner")
    owner = _make_user(db_session, org)

    login_as(client, owner)
    resp = client.get(f"/api/gdpr/export/{owner.id}")

    assert resp.status_code == 200
    assert resp.get_json()["profile"]["email"] == owner.email


def test_other_non_admin_cannot_export_someone_elses_data(
    db_session, make_org, client, login_as
):
    org = make_org("gdpr-same-org")
    owner = _make_user(db_session, org)
    attacker = _make_user(db_session, org)

    login_as(client, attacker)
    resp = client.get(f"/api/gdpr/export/{owner.id}")

    assert resp.status_code == 403
    assert owner.email not in resp.get_data(as_text=True)


def test_non_admin_cannot_export_across_organisations(
    db_session, make_org, client, login_as
):
    victim = _make_user(db_session, make_org("gdpr-org-a"))
    attacker = _make_user(db_session, make_org("gdpr-org-b"))

    login_as(client, attacker)
    resp = client.get(f"/api/gdpr/export/{victim.id}")

    assert resp.status_code == 403
    assert victim.email not in resp.get_data(as_text=True)


def test_platform_admin_can_export_any_user(db_session, make_org, client, login_as):
    victim = _make_user(db_session, make_org("gdpr-org-c"))
    admin = _make_user(db_session, make_org("gdpr-org-d"), platform_admin=True)

    login_as(client, admin)
    resp = client.get(f"/api/gdpr/export/{victim.id}")

    assert resp.status_code == 200
    assert resp.get_json()["profile"]["id"] == victim.id


def test_anonymous_cannot_export(db_session, make_org, client, login_as):
    owner = _make_user(db_session, make_org("gdpr-anon"))

    # Clear any cached identity so this really is an anonymous request.
    login_as(client, owner)
    with client.session_transaction() as sess:
        sess.clear()
    from flask import g, has_app_context

    if has_app_context():
        for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
            if hasattr(g, cached):
                delattr(g, cached)

    resp = client.get(f"/api/gdpr/export/{owner.id}")

    assert resp.status_code in (302, 401)
    assert owner.email not in resp.get_data(as_text=True)


def test_other_non_admin_cannot_read_status(db_session, make_org, client, login_as):
    org = make_org("gdpr-status")
    owner = _make_user(db_session, org)
    attacker = _make_user(db_session, org)

    login_as(client, attacker)
    assert client.get(f"/api/gdpr/status/{owner.id}").status_code == 403

    login_as(client, owner)
    assert client.get(f"/api/gdpr/status/{owner.id}").status_code == 200


# ---------------------------------------------------------------------------
# 3. Erasure — platform admin only
# ---------------------------------------------------------------------------


def test_non_admin_cannot_erase_another_user(db_session, make_org, client, login_as):
    org = make_org("gdpr-erase-deny")
    victim = _make_user(db_session, org)
    attacker = _make_user(db_session, org)
    victim_email = victim.email

    login_as(client, attacker)
    resp = client.post(f"/api/gdpr/delete/{victim.id}")

    assert resp.status_code == 403
    db_session.refresh(victim)
    assert victim.email == victim_email


def test_non_admin_cannot_erase_themselves(db_session, make_org, client, login_as):
    """Self-erasure is deliberately not self-service — an unconfirmed
    self-delete is its own hazard, so the platform-admin gate applies here too."""
    user = _make_user(db_session, make_org("gdpr-erase-self"))
    email = user.email

    login_as(client, user)
    resp = client.post(f"/api/gdpr/delete/{user.id}")

    assert resp.status_code == 403
    db_session.refresh(user)
    assert user.email == email


def test_anonymous_cannot_erase(db_session, make_org, client, login_as):
    victim = _make_user(db_session, make_org("gdpr-erase-anon"))
    email = victim.email

    with client.session_transaction() as sess:
        sess.clear()
    from flask import g, has_app_context

    if has_app_context():
        for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
            if hasattr(g, cached):
                delattr(g, cached)

    resp = client.post(f"/api/gdpr/delete/{victim.id}")

    assert resp.status_code in (302, 401, 403)
    db_session.refresh(victim)
    assert victim.email == email


def test_platform_admin_can_erase_and_credentials_are_destroyed(
    db_session, make_org, client, login_as
):
    victim = _make_user(db_session, make_org("gdpr-erase-ok"))
    admin = _make_user(db_session, make_org("gdpr-erase-admin"), platform_admin=True)

    login_as(client, admin)
    resp = client.post(f"/api/gdpr/delete/{victim.id}")

    assert resp.status_code == 200
    assert resp.get_json() == {"status": "deleted"}

    db_session.refresh(victim)
    assert victim.email is None
    assert victim.first_name is None
    assert victim.last_name is None
    # Nulling the email is not erasure on its own: app/auth/sso.py resolves an
    # SSO login by (external_id, sso_provider) before it ever consults the
    # email, so leaving those set would let an "erased" subject sign back in.
    assert victim.password_hash is None
    assert victim.external_id is None
    assert victim.sso_provider is None
