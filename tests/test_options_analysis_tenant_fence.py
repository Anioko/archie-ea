"""Vendor options analyses carry a tenant column and are fenced to their organisation.

``OptionsAnalysis`` and ``StakeholderInput`` had no ``organization_id`` and no ``TenantMixin``,
so nothing filtered them. Its routes allowed "the owner or any admin" with no organisation test,
so an admin of one organisation could read, patch and delete another organisation's analyses by
id (27 read sites), and sequential ids made that easy. ``capability_id`` is NOT NULL and points
at a tenant-fenced table, so the tenant is derived from the capability.
"""

from __future__ import annotations

import uuid

PASSWORD = "test-password-123"


def _org(db_session, label):
    from app.models.organization import Organization

    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"OA {label} {suffix}", slug=f"oa-{label}-{suffix}")
    db_session.add(org)
    db_session.flush()
    return org


def _user(db_session, org, *, role_name):
    from app.models.org_role import OrgRole
    from app.models.user import Role, User

    Role.insert_roles()
    role = Role.query.filter_by(name=role_name).first()
    suffix = uuid.uuid4().hex[:6]
    user = User(
        first_name="OA", last_name=f"User-{suffix}", email=f"oa-{suffix}@example.test",
        password=PASSWORD, confirmed=True, organization_id=org.id, role=role,
        is_org_admin=False, is_platform_admin=False,
    )
    db_session.add(user)
    db_session.flush()
    OrgRole.set_role(org.id, user.id, "viewer", granted_by_id=user.id)
    db_session.flush()
    return user


def _analysis(db_session, org, creator):
    from app.models.business_capability import BusinessCapability
    from app.models.vendor_analysis import OptionsAnalysis

    capability = BusinessCapability(name=f"Cap {uuid.uuid4().hex[:6]}", organization_id=org.id)
    db_session.add(capability)
    db_session.flush()
    extra = {"organization_id": org.id} if hasattr(OptionsAnalysis, "organization_id") else {}
    analysis = OptionsAnalysis(
        name="Tenant analysis", capability_id=capability.id, created_by_id=creator.id, **extra
    )
    db_session.add(analysis)
    db_session.flush()
    return analysis


# -- the fence, through the routes ---------------------------------------------------


def test_an_admin_of_another_organisation_cannot_read_patch_or_delete_an_analysis(
    app, db_session, login_as, client
):
    from sqlalchemy import text

    org_a, org_b = _org(db_session, "a"), _org(db_session, "b")
    intruder = _user(db_session, org_a, role_name="Administrator")
    owner = _user(db_session, org_b, role_name="User")
    analysis = _analysis(db_session, org_b, owner)
    db_session.commit()
    analysis_id = analysis.id
    login_as(client, intruder)
    # A real request starts with an empty session. Session.get() answers from the identity map
    # without running a query, which is the one path the tenant filter cannot see, so clear it.
    db_session.expunge_all()
    base = f"/dashboard/api/vendor-analysis/{analysis_id}"

    assert client.get(base).status_code == 404
    assert client.patch(base, json={"name": "hijacked"}).status_code == 404
    assert client.delete(base).status_code == 404
    # Plain SQL: reading it back through the ORM would itself be fenced to the caller's organisation.
    name = db_session.execute(
        text("SELECT name FROM options_analysis WHERE id = :id"), {"id": analysis_id}
    ).scalar()
    assert name == "Tenant analysis"


def test_the_owner_still_reads_their_own_analysis(app, db_session, login_as, client):
    org = _org(db_session, "own")
    owner = _user(db_session, org, role_name="User")
    analysis = _analysis(db_session, org, owner)
    db_session.commit()

    login_as(client, owner)

    assert client.get(f"/dashboard/api/vendor-analysis/{analysis.id}").status_code == 200


def test_an_admin_still_reads_an_analysis_in_their_own_organisation(app, db_session, login_as, client):
    org = _org(db_session, "same")
    owner = _user(db_session, org, role_name="User")
    admin = _user(db_session, org, role_name="Administrator")
    analysis = _analysis(db_session, org, owner)
    db_session.commit()

    login_as(client, admin)

    assert client.get(f"/dashboard/api/vendor-analysis/{analysis.id}").status_code == 200


# -- the column ----------------------------------------------------------------------


def test_a_new_analysis_and_input_are_stamped_with_the_callers_organisation(app, db_session):
    from app.models.business_capability import BusinessCapability
    from app.models.vendor_analysis import OptionsAnalysis, StakeholderInput

    org = _org(db_session, "stamp")
    creator = _user(db_session, org, role_name="User")
    capability = BusinessCapability(name="Stamp cap", organization_id=org.id)
    db_session.add(capability)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        analysis = OptionsAnalysis(name="Stamped", capability_id=capability.id, created_by_id=creator.id)
        db_session.add(analysis)
        db_session.flush()
        entry = StakeholderInput(analysis_id=analysis.id, stakeholder_id=creator.id, stakeholder_role="technical")
        db_session.add(entry)
        db_session.flush()

        assert analysis.organization_id == org.id
        assert entry.organization_id == org.id


# -- the backfill --------------------------------------------------------------------


def test_the_backfill_derives_each_tenant_from_the_capability_and_never_guesses(app):
    """Runs the two derivation statements against a scratch schema, so no real table is touched."""
    from sqlalchemy import text

    from app import db
    from app.commands import backfill_layer_tenancy as backfill

    assert {"options_analysis", "stakeholder_inputs"} <= backfill._PROVENANCE_ONLY
    schema = "tmp_oa_" + uuid.uuid4().hex[:8]
    with app.app_context():
        with db.engine.connect() as conn:
            trans = conn.begin()
            try:
                conn.execute(text(f"CREATE SCHEMA {schema}"))
                conn.execute(text(f"SET LOCAL search_path TO {schema}"))
                conn.execute(text("CREATE TABLE business_capability (id int, organization_id int)"))
                conn.execute(text("CREATE TABLE options_analysis (id int, capability_id int, organization_id int)"))
                conn.execute(text("CREATE TABLE stakeholder_inputs (id int, analysis_id int, organization_id int)"))
                conn.execute(text("INSERT INTO business_capability VALUES (1, 10), (2, NULL)"))
                conn.execute(text("INSERT INTO options_analysis VALUES (100, 1, NULL), (101, 2, NULL)"))
                conn.execute(text("INSERT INTO stakeholder_inputs VALUES (1000, 100, NULL), (1001, 101, NULL)"))

                conn.execute(text(backfill._DERIVABLE_ORG["options_analysis"]))
                conn.execute(text(backfill._DERIVABLE_ORG["stakeholder_inputs"]))

                analyses = dict(conn.execute(text("SELECT id, organization_id FROM options_analysis")).all())
                inputs = dict(conn.execute(text("SELECT id, organization_id FROM stakeholder_inputs")).all())
            finally:
                trans.rollback()

    assert analyses == {100: 10, 101: None}
    assert inputs == {1000: 10, 1001: None}
