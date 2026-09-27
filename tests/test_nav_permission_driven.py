"""F-11 regression: the sidebar never shows a link the user cannot reach.

The 2 Sep 2026 browser audit found sidebar/workspace links leading straight to
403 for the very role they were shown to. Root cause: navigation was keyed off
enterprise_role while the routes gate on Permission.ADMINISTER (@admin_required)
or the is_platform_admin super-admin flag (@platform_admin_required) — two
different vocabularies. get_sidebar_zones now drives visibility from the same
predicate each route checks: the admin zone needs user.is_admin(); a link may
declare requires="admin" | "platform_admin" and is dropped when unmet.
"""

import uuid

import pytest

from app.models.user import Role, User
from app.utils.role_access import get_sidebar_zones


def _endpoints(zones):
    return {link["endpoint"] for z in zones for link in z["links"]}


def _zone_names(zones):
    return {z["zone"] for z in zones}


def _admin_role(db_session):
    Role.insert_roles()  # seeds Administrator WITH Permission.ADMINISTER
    return Role.query.filter_by(name="Administrator").first()


@pytest.mark.usefixtures("db_session")
def test_security_architect_sees_read_only_governance_gates(db_session, make_org, tenant_ctx):
    org = make_org("nav")
    with tenant_ctx(org.id):
        user = User(email=f"sec-{uuid.uuid4().hex[:8]}@example.com", organization_id=org.id,
                    enterprise_role="security_architect", confirmed=True)
        db_session.add(user)
        db_session.flush()
        eps = _endpoints(get_sidebar_zones(user))
        # Security architects inspect gate policy through an explicitly
        # read-only page/list contract. Mutation remains ADMINISTER-only and is
        # exercised independently by the persona journey regression.
        assert "admin.governance_gates" in eps


@pytest.mark.usefixtures("db_session")
def test_super_admin_flag_without_administrator_role_gets_no_admin_zone(db_session, make_org, tenant_ctx):
    """The audited shape: is_platform_admin=True but Role=Architect. Every admin
    route is @admin_required, so showing the zone was seven 403 dead ends."""
    org = make_org("nav")
    with tenant_ctx(org.id):
        user = User(email=f"flag-{uuid.uuid4().hex[:8]}@example.com", organization_id=org.id,
                    enterprise_role="platform_admin", confirmed=True)
        user.is_platform_admin = True
        db_session.add(user)
        db_session.flush()
        assert not user.is_admin()
        assert "admin" not in _zone_names(get_sidebar_zones(user))


@pytest.mark.usefixtures("db_session")
def test_administrator_sees_admin_zone_but_organizations_needs_super_flag(db_session, make_org, tenant_ctx):
    org = make_org("nav")
    with tenant_ctx(org.id):
        role = _admin_role(db_session)
        user = User(email=f"admin-{uuid.uuid4().hex[:8]}@example.com", organization_id=org.id,
                    enterprise_role="platform_admin", confirmed=True)
        user.role = role
        db_session.add(user)
        db_session.flush()
        assert user.is_admin()

        zones = get_sidebar_zones(user)
        assert "admin" in _zone_names(zones)
        # organizations is @platform_admin_required — hidden without the flag
        assert "admin.organizations_list" not in _endpoints(zones)

        user.is_platform_admin = True
        db_session.flush()
        assert "admin.organizations_list" in _endpoints(get_sidebar_zones(user))


def test_zone_constants_are_not_mutated_by_filtering(db_session, make_org, tenant_ctx):
    """Filtering must build new dicts; the module-level zones are shared."""
    from app.utils import role_access

    org = make_org("nav")
    with tenant_ctx(org.id):
        before = {k: [len(z["links"]) for z in v] for k, v in role_access.SIDEBAR_ZONES.items()}
        user = User(email=f"sec2-{uuid.uuid4().hex[:8]}@example.com", organization_id=org.id,
                    enterprise_role="security_architect", confirmed=True)
        db_session.add(user)
        db_session.flush()
        get_sidebar_zones(user)
        after = {k: [len(z["links"]) for z in v] for k, v in role_access.SIDEBAR_ZONES.items()}
        assert before == after
