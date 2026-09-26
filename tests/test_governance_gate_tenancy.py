"""Governance gate names are unique per organisation, not platform-wide.

Each organisation overrides a system-default gate by name, so two
organisations must be able to hold a gate with the same name, while one
organisation still cannot hold two. ``scope_gate_names`` brings a database
created with the old platform-wide constraint into line.
"""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.usefixtures("db_session")


def _gate(db_session, name):
    from app.models.governance_gates import GovernanceGate

    gate = GovernanceGate(gate_name=name, min_completeness=70)
    db_session.add(gate)
    db_session.flush()
    return gate


def test_two_organisations_may_use_the_same_gate_name(db_session, make_org, tenant_ctx):
    from app.models.governance_gates import GovernanceGate

    first, second = make_org("gate-a"), make_org("gate-b")
    with tenant_ctx(first.id):
        mine = _gate(db_session, "arb_submission_shared")
    with tenant_ctx(second.id):
        theirs = _gate(db_session, "arb_submission_shared")
        visible = GovernanceGate.query.filter_by(gate_name="arb_submission_shared").all()
    assert mine.organization_id == first.id and theirs.organization_id == second.id
    assert [g.id for g in visible] == [theirs.id]


def test_one_organisation_cannot_hold_the_same_gate_name_twice(db_session, make_org, tenant_ctx):
    org = make_org("gate-dup")
    with tenant_ctx(org.id):
        _gate(db_session, "arb_submission_dup")
        with pytest.raises(IntegrityError):
            with db_session.begin_nested():
                _gate(db_session, "arb_submission_dup")


def test_scope_command_replaces_the_platform_wide_constraint(db_session):
    from app.commands.scope_governance_gate_names import (
        NEW_CONSTRAINT,
        OLD_CONSTRAINT,
        scope_gate_names,
    )

    conn = db_session.connection()
    # Put the table back the way older databases have it. Everything here,
    # including the row removal that lets the old constraint be re-created on a
    # shared database, is rolled back at teardown.
    conn.execute(text("DELETE FROM governance_gates"))
    conn.execute(text(f'ALTER TABLE governance_gates DROP CONSTRAINT IF EXISTS "{NEW_CONSTRAINT}"'))
    conn.execute(text(f'ALTER TABLE governance_gates DROP CONSTRAINT IF EXISTS "{OLD_CONSTRAINT}"'))
    conn.execute(text(f'ALTER TABLE governance_gates ADD CONSTRAINT "{OLD_CONSTRAINT}" UNIQUE (gate_name)'))

    assert scope_gate_names(conn) == [f"added {NEW_CONSTRAINT}", f"dropped {OLD_CONSTRAINT}"]
    names = {u["name"] for u in inspect(conn).get_unique_constraints("governance_gates")}
    assert NEW_CONSTRAINT in names and OLD_CONSTRAINT not in names
    assert scope_gate_names(conn) == []
