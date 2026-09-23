"""Cross-tenant isolation for compliance_policies/compliance_violations.

Before TenantMixin, `enterprise_crud_routes.py` queried/counted/created
CompliancePolicy and ComplianceViolation rows with no org filter at all, and
CompliancePolicy.name carried a GLOBAL unique=True — two organizations could
not both have a "NIST" policy, the same cross-tenant collision shape closed
for SSOGroupRoleMapping (PR#102). ComplianceControl is deliberately NOT
touched here: it is global regulatory-framework reference data (NIST-800-53
AC-2, ISO 27001 A.9.2.1 etc.), not per-org data — see its own docstring.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _make_policy(db_session, org_id, name):
    from app.models.compliance_models import CompliancePolicy

    row = CompliancePolicy(name=name, policy_type="NIST", organization_id=org_id)
    db_session.add(row)
    db_session.flush()
    return row


def _make_violation(db_session, org_id, policy_id, description="test violation"):
    from app.models.compliance_models import ComplianceViolation

    row = ComplianceViolation(
        policy_id=policy_id,
        description=description,
        organization_id=org_id,
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_compliance_policy_select_is_scoped_to_current_org(db_session, make_org, tenant_ctx):
    """The specific leak this fix closes: org A must not see org B's compliance
    policies when enterprise_crud_routes.py queries CompliancePolicy with no filter."""
    from app.models.compliance_models import CompliancePolicy

    org_a, org_b = make_org("a"), make_org("b")
    _make_policy(db_session, org_a.id, "NIST 800-53")
    b_policy = _make_policy(db_session, org_b.id, "ISO 27001")

    with tenant_ctx(org_a.id):
        visible_ids = {p.id for p in CompliancePolicy.query.all()}

    assert b_policy.id not in visible_ids, (
        "TENANT LEAK: org A can see org B's compliance policy."
    )


def test_two_orgs_can_use_the_same_policy_name(db_session, make_org, tenant_ctx):
    """Direct regression for the collision the old global unique=True caused:
    both orgs must be able to have their own "NIST" policy independently."""
    from app.models.compliance_models import CompliancePolicy

    org_a, org_b = make_org("a"), make_org("b")
    a_policy = _make_policy(db_session, org_a.id, "NIST")
    b_policy = _make_policy(db_session, org_b.id, "NIST")

    assert a_policy.id != b_policy.id
    with tenant_ctx(org_a.id):
        assert {p.id for p in CompliancePolicy.query.filter_by(name="NIST").all()} == {a_policy.id}
    with tenant_ctx(org_b.id):
        assert {p.id for p in CompliancePolicy.query.filter_by(name="NIST").all()} == {b_policy.id}


def test_compliance_violation_select_is_scoped_to_current_org(db_session, make_org, tenant_ctx):
    """Violations carry affected_system/root_cause/evidence_link — real
    per-org security-posture data, not reference content."""
    from app.models.compliance_models import ComplianceViolation

    org_a, org_b = make_org("a"), make_org("b")
    a_policy = _make_policy(db_session, org_a.id, "NIST")
    b_policy = _make_policy(db_session, org_b.id, "NIST")
    _make_violation(db_session, org_a.id, a_policy.id, "org a violation")
    b_violation = _make_violation(db_session, org_b.id, b_policy.id, "org b violation")

    with tenant_ctx(org_a.id):
        visible_ids = {v.id for v in ComplianceViolation.query.all()}

    assert b_violation.id not in visible_ids, (
        "TENANT LEAK: org A can read org B's compliance violation, "
        "including affected_system/root_cause/evidence_link."
    )


def test_compliance_control_remains_global_reference_data(db_session, make_org, tenant_ctx):
    """ComplianceControl is deliberately NOT tenant-scoped — it is the shared
    regulatory-framework catalog (control_code/title per framework), not
    per-org data. This test documents that decision so a future session
    doesn't "fix" it without re-reading why."""
    from app.models.compliance_models import ComplianceControl

    assert not hasattr(ComplianceControl, "organization_id"), (
        "ComplianceControl gained an organization_id — if this is intentional, "
        "update this test and the tier-1 checklist row together; if not, revert."
    )
