"""What ``require_roles`` actually admits, on the 153 routes that use it.

Two findings are pinned here. The first is fixed; the second is not, because
fixing it is a product decision about who loses access, not a defect with one
obvious repair.

**Fixed — enterprise_role was never read.** ``enterprise_role`` is the persona
the product is organised around: it drives the sidebar, the dashboard cards and
the AI charters. The live decorator (``app/_decorators_base.py``) read
``roles``, ``role_names``, ``role`` and ``role_archetype``, and not that. So the
fifteen routes naming ``business_architect`` in their allow-list — added on the
reasoning that "these modules exist for that persona" — could never be
satisfied *by being a business architect*. They were reachable only by accident,
through the second finding.

**Not fixed — the default Role makes an "architect" allow-list a no-op.**
``Role('Architect')`` is the row with ``default=True`` and ``User.__init__``
assigns it to every user it creates. ``require_roles`` normalises and reads
``role.name``, so **every authenticated account** satisfies any allow-list
containing "architect" — 71 routes guarded by ``("admin", "architect")`` plus
the 15 above. A ``procurement`` user can write to them today.

That is encoded below as a strict xfail rather than repaired. Tightening it
means deciding which existing users lose write access across 86 routes, and
getting that wrong locks people out of the platform. The strict marker means
the test *fails* the moment someone does tighten it, forcing the decision to be
made deliberately and this note to be updated.

There is also a dead second copy of this decorator at
``app/core/auth/decorators.py``. Nothing outside ``app/core/auth/__init__.py``
imports it, and it does not normalise the ``<Role 'x'>`` repr the live one
handles. It is not the code that runs.
"""

from __future__ import annotations

import io
import uuid

import pytest

# A route guarded by exactly ("admin", "architect", "business_architect").
GUARDED_URL = "/capability-map/import/preview"


def _user(db_session, org_id, *, enterprise_role=None):
    from app.models.user import User

    user = User(
        email=f"roles-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Role",
        last_name="Probe",
        organization_id=org_id,
        confirmed=True,
        enterprise_role=enterprise_role,
    )
    db_session.add(user)
    db_session.commit()
    return user.id


def _as(app, user_id):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True

    # Flask-Login caches the resolved user on `g`, and pytest-flask reuses one
    # context across the test; without clearing it a second login silently runs
    # as the first user.
    from flask import g, has_app_context

    if has_app_context():
        for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
            if hasattr(g, cached):
                delattr(g, cached)
    return client


def _post_a_file(client):
    return client.post(
        GUARDED_URL,
        data={"file": (io.BytesIO(b"name\nProbe Capability\n"), "probe.csv")},
        content_type="multipart/form-data",
    )


@pytest.fixture(autouse=True)
def _no_csrf(app):
    previous = app.config.get("WTF_CSRF_ENABLED", True)
    app.config["WTF_CSRF_ENABLED"] = False
    try:
        yield
    finally:
        app.config["WTF_CSRF_ENABLED"] = previous


def test_enterprise_role_is_one_of_the_sources_require_roles_reads():
    """The fix, asserted against the decorator rather than through a route.

    Through a route this would pass either way today, because the default
    Role('Architect') admits everybody — so the route-level test below cannot
    tell whether enterprise_role is read at all.
    """
    import inspect

    from app import _decorators_base

    source = inspect.getsource(_decorators_base.require_roles)
    assert "enterprise_role" in source, (
        "require_roles ignores enterprise_role, so the 15 routes naming "
        "business_architect in their allow-list cannot be satisfied by being one"
    )


def test_a_business_architect_can_reach_a_route_named_for_them(
    app, db_session, make_org, tenant_ctx
):
    org = make_org(f"roles-ba-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        user_id = _user(db_session, org.id, enterprise_role="business_architect")

    resp = _post_a_file(_as(app, user_id))

    assert resp.status_code != 403
    assert resp.status_code == 200


def test_an_anonymous_request_is_refused(app):
    resp = _post_a_file(app.test_client())
    # @login_required runs first and redirects to the login page; that or a 401
    # is correct, a 200 never is.
    assert resp.status_code in (302, 401), resp.status_code


@pytest.mark.xfail(
    strict=True,
    reason="Role('Architect') is default=True and User.__init__ assigns it to every "
           "user, so any allow-list containing 'architect' admits everyone. "
           "Tightening this decides who loses write access across 86 routes — see "
           "this module's docstring. When it is tightened, this xfail flips to a "
           "failure and must be removed.",
)
def test_an_unrelated_persona_is_refused(app, db_session, make_org, tenant_ctx):
    org = make_org(f"roles-deny-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        user_id = _user(db_session, org.id, enterprise_role="procurement")

    resp = _post_a_file(_as(app, user_id))

    assert resp.status_code == 403, (
        "procurement is not in this route's allow-list, but the default "
        "Role('Architect') every account carries satisfies 'architect'"
    )


def test_the_default_role_is_architect_and_every_user_gets_it(
    app, db_session, make_org, tenant_ctx
):
    """The premise of the xfail above, asserted so it cannot rot silently."""
    from app.models.user import Role, User

    default_role = Role.query.filter_by(default=True).first()
    assert default_role is not None
    assert default_role.name.lower() == "architect"

    org = make_org(f"roles-default-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        user_id = _user(db_session, org.id, enterprise_role="procurement")
        assert db_session.get(User, user_id).role is default_role, (
            "if new users no longer receive the default role, the xfail above "
            "may already be fixable"
        )
