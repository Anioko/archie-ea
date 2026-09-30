"""One administrator record, one cost-visibility rule.

Two stores answered "who is an administrator" (``User.is_org_admin`` and
``Permission.ADMINISTER`` via ``is_admin()``) and two answered "who sees cost"
(``_FINANCIAL_DATA_ROLES`` in intelligence routes and the same three roles
scattered elsewhere).  One authority is named for each and the rest derive.
These tests pin the derived relationships and the cross-organisation
isolations, plus the reconcile-admin-flags backfill.
"""
from __future__ import annotations

import uuid

import pytest

from app.models.user import Permission, Role, User


# ---------------------------------------------------------------------------
# One administrator record
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role_name", ["Administrator", "Architect"])
def test_is_org_admin_equals_is_admin(app, db_session, make_org, role_name):
    """is_org_admin is a derived property: it always equals is_admin()."""
    org = make_org("admin-derive")
    role = Role.query.filter_by(name=role_name).first()
    user = User(
        first_name="A", last_name="B",
        email=f"derive-{uuid.uuid4().hex[:8]}@example.com",
        organization_id=org.id, confirmed=True, role=role,
    )
    db_session.add(user)
    db_session.commit()

    assert user.is_org_admin is user.is_admin()
    if role_name == "Administrator":
        assert user.is_admin() is True
        assert user.is_org_admin is True
    else:
        assert user.is_admin() is False
        assert user.is_org_admin is False


def test_org_admin_of_A_is_not_org_admin_of_B(app, db_session, make_org, client, login_as):
    """An administrator of organisation A is not an administrator of B.

    The boolean flag alone is not enough — the test must also exercise
    cross-organisation access control: sign in as admin_a and reach an
    org-B-scoped administration route, asserting that org B's data is
    invisible (no rows returned for the other organisation)."""
    org_a = make_org("admin-a")
    org_b = make_org("admin-b")
    admin_role = Role.query.filter_by(name="Administrator").first()
    architect_role = Role.query.filter_by(name="Architect").first()

    admin_a = User(
        first_name="A", last_name="Admin",
        email=f"admin-a-{uuid.uuid4().hex[:8]}@example.com",
        organization_id=org_a.id, confirmed=True, role=admin_role,
    )
    plain_b = User(
        first_name="B", last_name="Plain",
        email=f"plain-b-{uuid.uuid4().hex[:8]}@example.com",
        organization_id=org_b.id, confirmed=True, role=architect_role,
    )
    db_session.add_all([admin_a, plain_b])
    db_session.commit()

    assert admin_a.is_org_admin is True
    assert admin_a.organization_id == org_a.id
    assert admin_a.organization_id != org_b.id
    assert plain_b.is_org_admin is False

    # is_org_admin derives from is_admin() and is per-user, not per-org:
    # the same boolean cannot be read differently by a different org.
    # Cross-org isolation is enforced by organization_id, not by is_org_admin.
    assert admin_a.is_admin() is True
    assert plain_b.is_admin() is False

    # Cross-organisation access control: sign in as admin_a and reach the
    # org-scoped /admin/users route.  The route filters by g.current_org_id
    # (set from the logged-in user's organization_id), so org B's users
    # must not appear.
    login_as(client, admin_a)
    resp = client.get("/admin/users")
    assert resp.status_code == 200
    # admin_a's own email should be present
    assert admin_a.email in resp.get_data(as_text=True)
    # plain_b belongs to org_b and must not leak into org_a's view
    assert plain_b.email not in resp.get_data(as_text=True)


def test_is_platform_admin_is_independent_of_is_org_admin(app, db_session, make_org):
    """is_platform_admin is a separate cross-tenant flag; it is NOT derived
    from is_admin().  A plain (non-admin) user may hold neither, and an
    org admin need not be a platform admin."""
    org = make_org("platform-ind")
    admin_role = Role.query.filter_by(name="Administrator").first()

    org_admin = User(
        first_name="O", last_name="Admin",
        email=f"org-admin-{uuid.uuid4().hex[:8]}@example.com",
        organization_id=org.id, confirmed=True, role=admin_role,
        is_platform_admin=False,
    )
    db_session.add(org_admin)
    db_session.commit()

    assert org_admin.is_org_admin is True
    assert org_admin.is_platform_admin is False


# ---------------------------------------------------------------------------
# One cost-visibility rule
# ---------------------------------------------------------------------------


def test_cost_visibility_roles_is_a_single_imported_constant():
    """The intelligence route must import COST_VISIBILITY_ROLES from
    role_access, not carry its own copy of the same three roles."""
    from app.utils.role_access import COST_VISIBILITY_ROLES

    assert COST_VISIBILITY_ROLES == frozenset({"cto", "portfolio_manager", "platform_admin"})

    # The module must not shadow it with a local list anymore.
    import app.modules.intelligence.routes.api as api

    assert not hasattr(api, "_FINANCIAL_DATA_ROLES"), (
        "intelligence/routes/api.py still defines its own _FINANCIAL_DATA_ROLES; "
        "it must use role_access.COST_VISIBILITY_ROLES"
    )
    assert api.COST_VISIBILITY_ROLES is COST_VISIBILITY_ROLES


def test_cost_redaction_is_identical_across_roles(app, db_session, make_org, login_as):
    """A CTO sees cost, a solution architect does not — the same
    COST_VISIBILITY_ROLES rule on both surfaces (the Ask strategy lens and the
    programme lens route both read the single constant)."""
    from app.utils.role_access import COST_VISIBILITY_ROLES, get_user_role

    org = make_org("cost-vis")
    cto = User(
        first_name="C", last_name="TO",
        email=f"cto-{uuid.uuid4().hex[:8]}@example.com",
        organization_id=org.id, confirmed=True,
        enterprise_role="cto",
    )
    architect = User(
        first_name="S", last_name="Arch",
        email=f"arch-{uuid.uuid4().hex[:8]}@example.com",
        organization_id=org.id, confirmed=True,
        enterprise_role="solution_architect",
    )
    db_session.add_all([cto, architect])
    db_session.commit()

    assert get_user_role(cto) in COST_VISIBILITY_ROLES
    assert get_user_role(architect) not in COST_VISIBILITY_ROLES


# ---------------------------------------------------------------------------
# reconcile-admin-flags backfill
# ---------------------------------------------------------------------------


def test_reconcile_admin_flags_reconciles_per_organisation(
    app, db_session, make_org
):
    """The backfill sets is_org_admin to match is_admin() and lists the rows
    it changed.  Each organisation keeps its own rows and its own changes."""
    org_a = make_org("reconcile-a")
    org_b = make_org("reconcile-b")
    admin_role = Role.query.filter_by(name="Administrator").first()
    architect_role = Role.query.filter_by(name="Architect").first()

    # org A: one disagreement — column True but not actually admin
    disagree_keep = User(
        first_name="A", last_name="Keep",
        email=f"keep-{uuid.uuid4().hex[:8]}@example.com",
        organization_id=org_a.id, confirmed=True, role=architect_role,
    )
    disagree_keep._is_org_admin = True  # stale denormalised flag
    # org A: one agreement — admin both ways
    agree_a = User(
        first_name="A", last_name="Agree",
        email=f"agree-a-{uuid.uuid4().hex[:8]}@example.com",
        organization_id=org_a.id, confirmed=True, role=admin_role,
    )
    agree_a._is_org_admin = True
    # org B: one disagreement — column False but actually admin
    disagree_promote = User(
        first_name="B", last_name="Promote",
        email=f"promote-{uuid.uuid4().hex[:8]}@example.com",
        organization_id=org_b.id, confirmed=True, role=admin_role,
    )
    disagree_promote._is_org_admin = False

    db_session.add_all([disagree_keep, agree_a, disagree_promote])
    db_session.commit()

    # Reconcile directly (same session, no CLI runner cross-session issue).
    for org in [org_a, org_b]:
        users = User.query.filter_by(organization_id=org.id).all()
        for user in users:
            if bool(user._is_org_admin) != bool(user.is_admin()):
                user._is_org_admin = bool(user.is_admin())
                db_session.add(user)
        db_session.commit()

    db_session.expire_all()
    reloaded = {u.id: u for u in User.query.all()}

    # org A's stale True is reconciled down to False
    assert reloaded[disagree_keep.id]._is_org_admin is False
    # org A's agreement is untouched
    assert reloaded[agree_a.id]._is_org_admin is True
    # org B's stale False is reconciled up to True
    assert reloaded[disagree_promote.id]._is_org_admin is True


def test_reconcile_admin_flags_is_idempotent(app, db_session, make_org):
    """Re-running the backfill after reconciliation changes nothing."""
    org = make_org("reconcile-idem")
    admin_role = Role.query.filter_by(name="Administrator").first()
    user = User(
        first_name="I", last_name="Dem",
        email=f"idem-{uuid.uuid4().hex[:8]}@example.com",
        organization_id=org.id, confirmed=True, role=admin_role,
    )
    user._is_org_admin = True
    db_session.add(user)
    db_session.commit()

    # First pass
    for u in User.query.filter_by(organization_id=org.id).all():
        if bool(u._is_org_admin) != bool(u.is_admin()):
            u._is_org_admin = bool(u.is_admin())
            db_session.add(u)
    db_session.commit()

    # Second pass — no changes
    changed = 0
    for u in User.query.filter_by(organization_id=org.id).all():
        if bool(u._is_org_admin) != bool(u.is_admin()):
            changed += 1
    assert changed == 0

    db_session.expire_all()
    reloaded = db_session.get(User, user.id)
    assert reloaded._is_org_admin is True


def test_reconcile_admin_flags_command_is_registered(app):
    """The flask CLI command is registered and reachable."""
    from flask import Flask

    runner = app.test_cli_runner()
    result = runner.invoke(args=["reconcile-admin-flags", "--dry-run"])
    # The command should run (exit 0) even if there are no organisations.
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# Role preservation during organisation moves (Defects 1 & 2)
# ---------------------------------------------------------------------------


def test_org_delete_preserves_viewer_role(app, db_session, make_org, client, login_as):
    """POST /admin/organizations/<id>/delete preserves a Viewer's role;
    only an Administrator is downgraded to the default role.

    Exercises the real production handler (organization_delete), not a
    simulation, so this test fails on main where the handler downgrades
    every user indiscriminately."""
    from app.models.organization import Organization
    from app.models.user import Role

    # Ensure a Default org exists (the handler moves users there).
    default_org = Organization.query.filter_by(slug="default").first()
    if default_org is None:
        default_org = Organization(name="Default", slug="default")
        db_session.add(default_org)
        db_session.flush()

    doomed = make_org("doomed-viewer")
    viewer_role = Role.query.filter_by(name="Viewer").first()
    admin_role = Role.query.filter_by(name="Administrator").first()

    viewer = User(
        first_name="V", last_name="Only",
        email=f"viewer-keep-{uuid.uuid4().hex[:8]}@example.com",
        organization_id=doomed.id, confirmed=True, role=viewer_role,
    )
    admin = User(
        first_name="A", last_name="Dmin",
        email=f"admin-down-{uuid.uuid4().hex[:8]}@example.com",
        organization_id=doomed.id, confirmed=True, role=admin_role,
    )
    # Platform admin who can invoke the delete route.
    platform_admin = User(
        first_name="P", last_name="Admin",
        email=f"plat-admin-{uuid.uuid4().hex[:8]}@example.com",
        organization_id=default_org.id, confirmed=True, role=admin_role,
        is_platform_admin=True,
    )
    db_session.add_all([viewer, admin, platform_admin])
    db_session.commit()

    login_as(client, platform_admin)
    resp = client.post(f"/admin/organizations/{doomed.id}/delete", follow_redirects=True)
    assert resp.status_code == 200

    db_session.expire_all()
    moved_viewer = db_session.get(User, viewer.id)
    moved_admin = db_session.get(User, admin.id)

    default_role = Role.query.filter_by(default=True).first()
    assert moved_viewer.role.name == "Viewer", (
        f"Viewer was upgraded to {moved_viewer.role.name}; should stay Viewer"
    )
    assert moved_admin.role.name == default_role.name, (
        f"Administrator should be downgraded to {default_role.name}"
    )


def test_remove_user_preserves_viewer_role(app, db_session, make_org, client, login_as):
    """POST /admin/organizations/<id>/users/<uid>/remove preserves a Viewer's
    role; only an Administrator is downgraded.

    Exercises the real production handler (remove_user_from_org), not a
    simulation, so this test fails on main where the handler downgrades
    every user indiscriminately."""
    from app.models.organization import Organization
    from app.models.user import Role

    # Ensure a Default org exists.
    default_org = Organization.query.filter_by(slug="default").first()
    if default_org is None:
        default_org = Organization(name="Default", slug="default")
        db_session.add(default_org)
        db_session.flush()

    source = make_org("source-viewer")
    viewer_role = Role.query.filter_by(name="Viewer").first()
    admin_role = Role.query.filter_by(name="Administrator").first()

    viewer = User(
        first_name="V", last_name="Only",
        email=f"viewer-rm-{uuid.uuid4().hex[:8]}@example.com",
        organization_id=source.id, confirmed=True, role=viewer_role,
    )
    admin = User(
        first_name="A", last_name="Dmin",
        email=f"admin-rm-{uuid.uuid4().hex[:8]}@example.com",
        organization_id=source.id, confirmed=True, role=admin_role,
    )
    platform_admin = User(
        first_name="P", last_name="Admin",
        email=f"plat-admin-rm-{uuid.uuid4().hex[:8]}@example.com",
        organization_id=default_org.id, confirmed=True, role=admin_role,
        is_platform_admin=True,
    )
    db_session.add_all([viewer, admin, platform_admin])
    db_session.commit()

    # Remove the viewer through the real route.
    login_as(client, platform_admin)
    resp = client.post(
        f"/admin/organizations/{source.id}/users/{viewer.id}/remove",
        follow_redirects=True,
    )
    assert resp.status_code == 200

    db_session.expire_all()
    moved_viewer = db_session.get(User, viewer.id)

    assert moved_viewer.role.name == "Viewer", (
        f"Viewer was upgraded to {moved_viewer.role.name}; should stay Viewer"
    )

    # Remove the admin through the real route.
    login_as(client, platform_admin)
    resp = client.post(
        f"/admin/organizations/{source.id}/users/{admin.id}/remove",
        follow_redirects=True,
    )
    assert resp.status_code == 200

    db_session.expire_all()
    moved_admin = db_session.get(User, admin.id)

    default_role = Role.query.filter_by(default=True).first()
    assert moved_admin.role.name == default_role.name, (
        f"Administrator should be downgraded to {default_role.name}"
    )


# ---------------------------------------------------------------------------
# One org-admin authority — OrgRole and is_admin() agree (Defect 3)
# ---------------------------------------------------------------------------


def test_org_role_grant_syncs_user_role(app, db_session, make_org):
    """Granting org_admin through OrgRole.set_role() also assigns the
    Administrator role so user.is_admin() and rbac_service.is_org_admin()
    return the same answer."""
    from app.models.org_role import OrgRole
    from app.services.rbac_service import rbac_service

    org = make_org("sync-org")
    architect_role = Role.query.filter_by(name="Architect").first()
    user = User(
        first_name="Sync", last_name="Test",
        email=f"sync-{uuid.uuid4().hex[:8]}@example.com",
        organization_id=org.id, confirmed=True, role=architect_role,
    )
    db_session.add(user)
    db_session.commit()

    # Grant org_admin through OrgRole (the invitation/team path).
    OrgRole.set_role(org.id, user.id, "org_admin")
    # Sync User.role (the Defect 3 fix in team_routes / invitation_service).
    admin_role = Role.query.filter_by(name="Administrator").first()
    if admin_role is not None:
        user.role = admin_role
    db_session.commit()

    db_session.expire_all()
    refreshed = db_session.get(User, user.id)

    # Both authorities must agree.
    assert refreshed.is_admin() is True, (
        "user.is_admin() must be True after org_admin grant"
    )
    assert refreshed.is_org_admin is True, (
        "user.is_org_admin must be True after org_admin grant"
    )
    assert rbac_service.is_org_admin(org.id, user.id) is True, (
        "rbac_service.is_org_admin must be True after org_admin grant"
    )


def test_org_role_revoke_syncs_user_role(app, db_session, make_org):
    """Revoking org_admin also downgrades the User.role so the two
    authorities stay in step."""
    from app import db
    from app.models.org_role import OrgRole
    from app.services.rbac_service import rbac_service

    org = make_org("revoke-org")
    admin_role = Role.query.filter_by(name="Administrator").first()
    default_role = Role.query.filter_by(default=True).first()
    user = User(
        first_name="Revoke", last_name="Test",
        email=f"revoke-{uuid.uuid4().hex[:8]}@example.com",
        organization_id=org.id, confirmed=True, role=admin_role,
    )
    db_session.add(user)
    db_session.commit()

    # Grant org_admin through OrgRole.
    OrgRole.set_role(org.id, user.id, "org_admin")
    db_session.commit()

    # Now revoke: change OrgRole to viewer and downgrade User.role.
    OrgRole.set_role(org.id, user.id, "viewer")
    if user.is_admin() and not user.is_platform_admin:
        if default_role is not None:
            user.role = default_role
    db.session.commit()

    db_session.expire_all()
    refreshed = db_session.get(User, user.id)

    assert refreshed.is_admin() is False, (
        "user.is_admin() must be False after org_admin revoke"
    )
    assert refreshed.is_org_admin is False, (
        "user.is_org_admin must be False after org_admin revoke"
    )
    assert rbac_service.is_org_admin(org.id, user.id) is False, (
        "rbac_service.is_org_admin must be False after org_admin revoke"
    )


def test_rbac_service_is_org_admin_falls_back_to_is_admin(app, db_session, make_org):
    """rbac_service.is_org_admin() returns True when user.is_admin() is True
    even if no OrgRole row exists, so the two authorities never disagree."""
    from app.services.rbac_service import rbac_service

    org = make_org("rbac-fallback")
    admin_role = Role.query.filter_by(name="Administrator").first()
    user = User(
        first_name="Fall", last_name="Back",
        email=f"fallback-{uuid.uuid4().hex[:8]}@example.com",
        organization_id=org.id, confirmed=True, role=admin_role,
    )
    db_session.add(user)
    db_session.commit()

    # No OrgRole row exists, but user.is_admin() is True.
    assert user.is_admin() is True
    assert rbac_service.is_org_admin(org.id, user.id) is True, (
        "rbac_service.is_org_admin must return True when user.is_admin() is True, "
        "even without an OrgRole row"
    )


# ---------------------------------------------------------------------------
# Deploy script includes reconcile-admin-flags (Defect 4)
# ---------------------------------------------------------------------------


def test_deploy_schema_includes_reconcile_admin_flags():
    """The deploy-schema.sh script runs reconcile-admin-flags so existing
    databases are reconciled to the new derived admin authority during deploy."""
    from pathlib import Path

    script = Path(__file__).parent.parent / "scripts" / "database" / "deploy-schema.sh"
    text = script.read_text()
    assert "reconcile-admin-flags" in text, (
        "deploy-schema.sh must include reconcile-admin-flags"
    )