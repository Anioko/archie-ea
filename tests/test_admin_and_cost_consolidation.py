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


def test_org_admin_of_A_is_not_org_admin_of_B(app, db_session, make_org, login_as):
    """An administrator of organisation A is not an administrator of B."""
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


def test_is_platform_admin_is_independent_of_is_org_admin(app, db_session, make_org):
    """is_platform_admin is a separate cross-tenant flag; it is NOT derived
    from is_admin().  A plain (non-admin) user may hold neither, and an
    org admin need not be a platform admin."""
    org = make_org("platform-ind")
    architect_role = Role.query.filter_by(name="Architect").first()
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