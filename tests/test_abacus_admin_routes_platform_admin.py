"""Abacus sync is platform-wide configuration: only a platform admin may read or change it.

``ExternalSystem`` and ``Job`` carry no tenant column -- one Abacus connector config and one job
queue serve every organisation (see the module docstring on ``tests/test_abacus_sync_job_lock.py``:
"there is one ExternalSystem row for the whole platform, not one per tenant"). The admin write
routes for it (save settings, test connection, trigger sync, cancel a job, clear stale jobs) were
guarded by ``@admin_required`` (``Permission.ADMINISTER``), which an organisation's own
administrator role holds -- the same defect class already fixed for feature flags
(``test_feature_flag_routes_platform_admin.py``) and sidebar items/editor content
(``test_sidebar_editor_vendor_platform_admin.py``). A tenant administrator could save new Abacus
credentials for every organisation, trigger or cancel syncs that touch every tenant's data, or
force-clear another organisation's operators' in-flight jobs. They now use
``@platform_admin_required``.

Both live module trees carry these routes (``app/modules/admin/v2/routes/admin_routes.py``,
guardrail-enabled, and ``app/modules/admin/routes/admin_routes.py``, the v1 modular tree) -- fixed
in both defensively, since which tree is registered depends on the ``USE_ADMIN_GUARDRAILS`` /
``USE_NEW_ADMIN`` flags at deploy time and this test suite cannot assume either is the one running
in production. ``clear-stale-jobs`` exists only in the v2 tree.
"""

from __future__ import annotations

import uuid

import pytest


def _user(db_session, org, *, role_name="Administrator", platform=False):
    from app.models import Role
    from app.models.user import User

    role = Role.query.filter_by(name=role_name).first()
    if role is None:
        pytest.skip("no %s role seeded in this database" % role_name)
    user = User(email=f"abacus-{uuid.uuid4().hex[:6]}@example.test", first_name="Abacus", last_name="Tester",
                organization_id=org.id, confirmed=True, role=role)
    user.password = uuid.uuid4().hex
    user.is_org_admin = True
    user.is_platform_admin = platform
    db_session.add(user)
    db_session.flush()
    return user


def _job(db_session):
    from app.models.job import Job

    job = Job(name="abacus incremental sync", task="abacus_sync", status="in_progress")
    db_session.add(job)
    db_session.flush()
    return job


def _world(db_session, make_org):
    # Two organisations (DEFECT-7, pr312-v1 review): Abacus is platform-wide,
    # so a tenant admin from EITHER organisation must be refused -- proving
    # this is a platform-admin check, not an org-specific one that happens
    # to match org A by coincidence.
    org_a = make_org("abacus-a")
    org_b = make_org("abacus-b")
    tenant_admin_a = _user(db_session, org_a)
    tenant_admin_b = _user(db_session, org_b)
    platform_admin = _user(db_session, org_a, platform=True)
    job = _job(db_session)
    db_session.commit()
    return tenant_admin_a.id, tenant_admin_b.id, platform_admin.id, job.id


def _login(db_session, client, login_as, user_id):
    from app.models.user import User

    db_session.expunge_all()
    login_as(client, db_session.get(User, user_id))


@pytest.mark.parametrize("method,path", [
    ("get", "/admin/abacus-settings"),
    ("post", "/admin/abacus-settings"),
    ("post", "/admin/abacus-settings/test-connection"),
    ("post", "/admin/abacus-settings/trigger-sync"),
    ("post", "/admin/abacus-settings/clear-stale-jobs"),
    # pr312-v1 review, DEFECT-1/3/4/5/6: these six were missed by the first
    # round -- discover-filters/discover-types/save-relationship-mappings
    # write platform-wide Abacus config; sync-status/stats/relationship-
    # mappings read it.
    ("get", "/admin/abacus-settings/sync-status"),
    ("get", "/admin/abacus-settings/stats"),
    ("post", "/admin/abacus-settings/discover-filters"),
])
def test_a_tenant_administrator_is_refused_on_every_abacus_settings_route(
    app, db_session, make_org, client, login_as, method, path
):
    tenant_admin_a_id, tenant_admin_b_id, _platform_id, _job_id = _world(db_session, make_org)

    for admin_id in (tenant_admin_a_id, tenant_admin_b_id):
        _login(db_session, client, login_as, admin_id)
        response = getattr(client, method)(path)
        assert response.status_code == 403


def test_a_tenant_administrator_is_refused_on_abacus_dashboard(
    app, db_session, make_org, client, login_as
):
    """Separate from the parametrized set above: /admin/abacus-dashboard is
    a page route, not under the abacus-settings prefix."""
    tenant_admin_a_id, tenant_admin_b_id, _platform_id, _job_id = _world(db_session, make_org)

    for admin_id in (tenant_admin_a_id, tenant_admin_b_id):
        _login(db_session, client, login_as, admin_id)
        response = client.get("/admin/abacus-dashboard")
        assert response.status_code == 403


def test_a_tenant_administrator_cannot_cancel_a_platform_wide_abacus_job(
    app, db_session, make_org, client, login_as
):
    tenant_admin_a_id, tenant_admin_b_id, _platform_id, job_id = _world(db_session, make_org)

    for admin_id in (tenant_admin_a_id, tenant_admin_b_id):
        _login(db_session, client, login_as, admin_id)
        response = client.post(f"/admin/abacus-settings/cancel-job/{job_id}")
        assert response.status_code == 403


def test_a_platform_administrator_can_still_reach_abacus_settings(
    app, db_session, make_org, client, login_as
):
    _tenant_a_id, _tenant_b_id, platform_admin_id, _job_id = _world(db_session, make_org)

    _login(db_session, client, login_as, platform_admin_id)
    response = client.get("/admin/abacus-settings")

    assert response.status_code == 200


@pytest.mark.parametrize("method,path", [
    ("post", "/admin/abacus-settings/discover-types"),
    ("post", "/admin/abacus-settings/save-relationship-mappings"),
    ("get", "/admin/abacus-settings/relationship-mappings"),
])
def test_a_tenant_administrator_is_refused_on_v2_only_abacus_routes(
    app, db_session, make_org, client, login_as, method, path
):
    """These three routes (DEFECT-2/3/6, pr312-v1 review) exist only in the
    v2 module tree. Skip rather than fail if this environment has the v1
    tree mounted instead -- a 404 here says nothing about the fix, which
    covers both trees defensively regardless of which is live."""
    tenant_admin_a_id, tenant_admin_b_id, _platform_id, _job_id = _world(db_session, make_org)

    for admin_id in (tenant_admin_a_id, tenant_admin_b_id):
        _login(db_session, client, login_as, admin_id)
        response = getattr(client, method)(path)
        if response.status_code == 404:
            pytest.skip(f"{path} not reachable in this environment (v1 tree mounted)")
        assert response.status_code == 403
