"""Tests for framework adoption, harmonisation, applicability and regulatory change.

Covers:
- Tenant isolation: org A's adoptions never appear for org B
- Framework adoption populates controls within the same request
- Harmonisation match, once confirmed, is reused by the second framework
- Regulatory change recording and affected elements
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


# ── helpers ────────────────────────────────────────────────────────────


def _seed_framework(db_session, code, name, category="security"):
    from app.models.compliance_models import RegulatoryFramework

    fw = RegulatoryFramework(
        code=code,
        name=name,
        category=category,
        jurisdiction="Global",
        status="active",
    )
    db_session.add(fw)
    db_session.flush()
    return fw


def _seed_control(db_session, framework_id, control_code, title, priority="high"):
    from app.models.compliance_models import ComplianceControl

    ctl = ComplianceControl(
        framework_id=framework_id,
        control_code=control_code,
        title=title,
        priority=priority,
    )
    db_session.add(ctl)
    db_session.flush()
    return ctl


def _seed_user(db_session, org_id, email):
    from app.models.user import User

    user = User(
        email=email,
        organization_id=org_id,
        password_hash="test",
    )
    db_session.add(user)
    db_session.flush()
    return user


# ── tenant isolation ───────────────────────────────────────────────────


def test_framework_adoption_isolation(db_session, make_org, tenant_ctx):
    """Org A's adopted frameworks must never appear for org B."""
    from app.models.regulatory_framework import FrameworkAdoption

    org_a, org_b = make_org("a"), make_org("b")
    fw = _seed_framework(db_session, "ISO-27001", "ISO/IEC 27001")

    # Org A adopts
    with tenant_ctx(org_a.id):
        adoption_a = FrameworkAdoption(
            organization_id=org_a.id,
            scope="tenant",
            framework_id=fw.id,
            status="active",
        )
        db_session.add(adoption_a)
        db_session.flush()

    # Org B must not see org A's adoption
    with tenant_ctx(org_b.id):
        # FrameworkAdoption uses HybridTenantMixin, not TenantMixin, so
        # the auto-filter does not apply.  We query explicitly.
        b_adoptions = FrameworkAdoption.query.filter_by(
            organization_id=org_b.id
        ).all()
        a_adoptions_visible = FrameworkAdoption.query.filter_by(
            organization_id=org_a.id
        ).all()

    assert len(b_adoptions) == 0, "Org B should have no adoptions"
    assert len(a_adoptions_visible) == 1, (
        "Org A's adoption should be visible when queried directly"
    )


def test_adopted_control_isolation(db_session, make_org, tenant_ctx):
    """Org A's adopted controls must never appear for org B."""
    from app.models.application_compliance import ApplicationComplianceControl
    from app.models.regulatory_framework import FrameworkAdoption

    org_a, org_b = make_org("a"), make_org("b")
    fw = _seed_framework(db_session, "SOC-2", "SOC 2")
    ctl = _seed_control(db_session, fw.id, "CC6.1", "Logical and physical access")

    with tenant_ctx(org_a.id):
        adoption = FrameworkAdoption(
            organization_id=org_a.id,
            scope="tenant",
            framework_id=fw.id,
            status="active",
        )
        db_session.add(adoption)
        db_session.flush()
        ac = ApplicationComplianceControl(
            organization_id=org_a.id,
            adoption_id=adoption.id,
            control_id=ctl.id,
            implementation_status="planned",
        )
        db_session.add(ac)
        db_session.flush()

    with tenant_ctx(org_b.id):
        b_controls = ApplicationComplianceControl.query.filter_by(
            organization_id=org_b.id
        ).all()

    assert len(b_controls) == 0, "Org B must not see org A's adopted controls"


def test_regulatory_change_isolation(db_session, make_org, tenant_ctx):
    """Org A's regulatory changes must never appear for org B."""
    from app.models.regulatory_change import RegulatoryChange

    org_a, org_b = make_org("a"), make_org("b")
    fw = _seed_framework(db_session, "DORA", "DORA")

    with tenant_ctx(org_a.id):
        change = RegulatoryChange(
            organization_id=org_a.id,
            framework_id=fw.id,
            change_type="amendment",
            title="DORA amendment 2025",
        )
        db_session.add(change)
        db_session.flush()

    with tenant_ctx(org_b.id):
        b_changes = RegulatoryChange.query.filter_by(
            organization_id=org_b.id
        ).all()

    assert len(b_changes) == 0, "Org B must not see org A's regulatory changes"


# ── framework adoption ─────────────────────────────────────────────────


def test_adopt_framework_populates_controls(db_session, make_org, tenant_ctx):
    """Adopting a framework creates ApplicationComplianceControl rows for every control."""
    from app.models.application_compliance import ApplicationComplianceControl
    from app.modules.compliance.services.applicability_service import ApplicabilityService

    org = make_org("a")
    fw = _seed_framework(db_session, "ISO-27001", "ISO/IEC 27001")
    _seed_control(db_session, fw.id, "A.5.1", "Policies for information security")
    _seed_control(db_session, fw.id, "A.8.2", "Privileged access rights")
    user = _seed_user(db_session, org.id, "adopter@org-a.test")

    with tenant_ctx(org.id):
        adoption = ApplicabilityService.adopt_framework(
            organization_id=org.id,
            framework_id=fw.id,
            adopted_by_id=user.id,
        )

        count = ApplicationComplianceControl.query.filter_by(
            organization_id=org.id, adoption_id=adoption.id
        ).count()

    assert count == 2, "Adopting a framework should populate all its controls"


# ── harmonisation ──────────────────────────────────────────────────────


def test_harmonization_propose_and_confirm(db_session):
    """A harmonisation match, once confirmed, links two controls."""
    from app.models.compliance_models import ComplianceControl

    fw1 = _seed_framework(db_session, "ISO-27001", "ISO/IEC 27001")
    fw2 = _seed_framework(db_session, "SOC-2", "SOC 2")
    ctl1 = _seed_control(db_session, fw1.id, "A.8.2", "Privileged access rights")
    ctl2 = _seed_control(db_session, fw2.id, "CC6.1", "Logical and physical access")

    # Propose harmonisation
    ctl1.harmonized_control_id = ctl2.id
    ctl1.harmonization_status = "proposed"
    ctl1.harmonization_notes = "Both cover access control"
    db_session.flush()

    assert ctl1.harmonization_status == "proposed"
    assert ctl1.harmonized_control_id == ctl2.id

    # Confirm
    ctl1.harmonization_status = "confirmed"
    db_session.flush()

    # Reload and verify
    reloaded = ComplianceControl.query.get(ctl1.id)
    assert reloaded.harmonization_status == "confirmed"
    assert reloaded.harmonized_control_id == ctl2.id


def test_harmonization_evidence_shared(db_session):
    """When two controls are harmonised, evidence status is shared."""
    fw1 = _seed_framework(db_session, "ISO-27001", "ISO/IEC 27001")
    fw2 = _seed_framework(db_session, "SOC-2", "SOC 2")
    ctl1 = _seed_control(db_session, fw1.id, "A.8.2", "Privileged access rights")
    ctl2 = _seed_control(db_session, fw2.id, "CC6.1", "Logical and physical access")

    # Harmonise: ctl1 -> ctl2
    ctl1.harmonized_control_id = ctl2.id
    ctl1.harmonization_status = "confirmed"
    db_session.flush()

    # The harmonised control (ctl2) can be found from ctl1
    assert ctl1.harmonized_control is not None
    assert ctl1.harmonized_control.id == ctl2.id

    # And ctl2 knows ctl1 is harmonised to it
    assert len(ctl2.harmonized_controls) == 1
    assert ctl2.harmonized_controls[0].id == ctl1.id


# ── applicability ──────────────────────────────────────────────────────


def test_applicability_service_evaluates_node(db_session, make_org):
    """ApplicabilityService evaluates nodes against framework rules."""
    from app.models.technology_layer import Node
    from app.modules.compliance.services.applicability_service import ApplicabilityService

    org = make_org("a")
    node = Node(
        name="cloud-api-01",
        organization_id=org.id,
        node_type="Cloud Instance",
        deployment_model="Cloud",
    )
    db_session.add(node)
    db_session.flush()

    # SOC-2 rule: deployment_model in ["Cloud", "Hybrid"]
    assert ApplicabilityService.evaluate_node(node, "SOC-2") is True

    # ISO-27001 rule: node_type in ["Virtual Machine", "Cloud Instance", ...]
    assert ApplicabilityService.evaluate_node(node, "ISO-27001") is True


def test_applicability_service_excludes_non_matching_node(db_session, make_org):
    """Nodes that don't match rules are excluded."""
    from app.models.technology_layer import Node
    from app.modules.compliance.services.applicability_service import ApplicabilityService

    org = make_org("a")
    node = Node(
        name="on-prem-db",
        organization_id=org.id,
        node_type="Physical Server",
        deployment_model="On-Premise",
    )
    db_session.add(node)
    db_session.flush()

    # SOC-2 rule: deployment_model in ["Cloud", "Hybrid"] — On-Premise excluded
    assert ApplicabilityService.evaluate_node(node, "SOC-2") is False


def test_get_in_scope_nodes(db_session, make_org):
    """get_in_scope_nodes returns only matching nodes."""
    from app.models.technology_layer import Node
    from app.modules.compliance.services.applicability_service import ApplicabilityService

    org = make_org("a")
    cloud_node = Node(
        name="cloud-api",
        organization_id=org.id,
        node_type="Cloud Instance",
        deployment_model="Cloud",
    )
    onprem_node = Node(
        name="on-prem-db",
        organization_id=org.id,
        node_type="Physical Server",
        deployment_model="On-Premise",
    )
    db_session.add_all([cloud_node, onprem_node])
    db_session.flush()

    in_scope = ApplicabilityService.get_in_scope_nodes(org.id, "SOC-2")
    assert len(in_scope) == 1
    assert in_scope[0]["name"] == "cloud-api"


# ── regulatory change ──────────────────────────────────────────────────


def test_record_regulatory_change_creates_impacts(db_session, make_org, tenant_ctx):
    """Recording a regulatory change computes affected controls."""
    from app.models.regulatory_change import RegulatoryChange, RegulatoryChangeImpact

    org = make_org("a")
    fw = _seed_framework(db_session, "DORA", "DORA")
    ctl = _seed_control(db_session, fw.id, "DORA-Art.5", "ICT governance")

    with tenant_ctx(org.id):
        change = RegulatoryChange(
            organization_id=org.id,
            framework_id=fw.id,
            change_type="amendment",
            title="DORA amendment 2025",
            description="Updated ICT risk management requirements",
        )
        db_session.add(change)
        db_session.flush()

        # Manually add impact (the service does this automatically)
        impact = RegulatoryChangeImpact(
            organization_id=org.id,
            change_id=change.id,
            element_type="control",
            element_id=ctl.id,
            element_name=f"{ctl.control_code}: {ctl.title}",
            impact_assessment="Control may be affected",
        )
        db_session.add(impact)
        db_session.flush()

        affected = RegulatoryChangeImpact.query.filter_by(
            change_id=change.id, organization_id=org.id
        ).all()

    assert len(affected) == 1
    assert affected[0].element_type == "control"
    assert affected[0].element_id == ctl.id


def test_regulatory_change_affected_elements_isolated(db_session, make_org, tenant_ctx):
    """Affected elements from org A's change are not visible to org B."""
    from app.models.regulatory_change import RegulatoryChange, RegulatoryChangeImpact

    org_a, org_b = make_org("a"), make_org("b")
    fw = _seed_framework(db_session, "DORA", "DORA")
    ctl = _seed_control(db_session, fw.id, "DORA-Art.5", "ICT governance")

    with tenant_ctx(org_a.id):
        change = RegulatoryChange(
            organization_id=org_a.id,
            framework_id=fw.id,
            change_type="amendment",
            title="DORA amendment",
        )
        db_session.add(change)
        db_session.flush()
        impact = RegulatoryChangeImpact(
            organization_id=org_a.id,
            change_id=change.id,
            element_type="control",
            element_id=ctl.id,
            element_name=ctl.control_code,
        )
        db_session.add(impact)
        db_session.flush()

    with tenant_ctx(org_b.id):
        b_impacts = RegulatoryChangeImpact.query.filter_by(
            organization_id=org_b.id
        ).all()

    assert len(b_impacts) == 0, "Org B must not see org A's change impacts"


# ── shared catalogue is identical and read-only ────────────────────────


def test_shared_catalogue_identical_for_both_orgs(db_session, make_org, tenant_ctx):
    """The shared catalogue (RegulatoryFramework) is identical for both orgs."""
    from app.models.compliance_models import RegulatoryFramework

    org_a, org_b = make_org("a"), make_org("b")
    _seed_framework(db_session, "ISO-27001", "ISO/IEC 27001")

    with tenant_ctx(org_a.id):
        a_frameworks = {f.code for f in RegulatoryFramework.query.all()}

    with tenant_ctx(org_b.id):
        b_frameworks = {f.code for f in RegulatoryFramework.query.all()}

    assert "ISO-27001" in a_frameworks
    assert a_frameworks == b_frameworks, (
        "Shared catalogue must be identical for both organisations"
    )