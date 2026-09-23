"""Tests for the control-gap and compliance-tag blocks on
``IntelligenceQueryService.risk_for_element`` (L6): beside the risks, the
``ComplianceGap`` rows recorded against anything on the answer's own element
set (the picked element plus its blast radii), filtered by a regulatory
framework code when the caller gives one, and the picked component's own
recorded compliance tags.

Fixtures (app, db_session, make_org, client, login_as) are discovered via
app/modules/intelligence/tests/conftest.py's own import of tests.conftest,
same pattern as the other lens test modules. No import needed here.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import event

# --- fixtures / helpers ------------------------------------------------------


def _element(db_session, org_id, name, layer="application", type_="ApplicationComponent"):
    from app.models import ArchiMateElement

    el = ArchiMateElement(name=name, type=type_, layer=layer, organization_id=org_id)
    db_session.add(el)
    db_session.flush()
    return el


def _relationship(db_session, org_id, source, target, type_="Serving"):
    from app.models import ArchiMateRelationship

    rel = ArchiMateRelationship(
        source_id=source.id, target_id=target.id, type=type_, organization_id=org_id
    )
    db_session.add(rel)
    db_session.flush()
    return rel


def _risk(db_session, org_id, element, *, title="Vendor lock-in", likelihood=4, impact=5):
    from app.models.risk import Risk

    row = Risk(
        organization_id=org_id,
        archimate_element_id=element.id,
        title=title,
        likelihood=likelihood,
        impact=impact,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _component(
    db_session,
    org_id,
    element_id,
    *,
    name="Comp",
    compliance_tags=None,
    gdpr_compliant=None,
    pii_data_processed=None,
    data_classification=None,
    compliance_requirements=None,
):
    from app.models.application_portfolio import ApplicationComponent

    kwargs = dict(name=name, organization_id=org_id, archimate_element_id=element_id)
    if compliance_tags is not None:
        kwargs["compliance_tags"] = compliance_tags
    if gdpr_compliant is not None:
        kwargs["gdpr_compliant"] = gdpr_compliant
    if pii_data_processed is not None:
        kwargs["pii_data_processed"] = pii_data_processed
    if data_classification is not None:
        kwargs["data_classification"] = data_classification
    if compliance_requirements is not None:
        kwargs["compliance_requirements"] = compliance_requirements
    row = ApplicationComponent(**kwargs)
    db_session.add(row)
    db_session.flush()
    return row


def _framework(db_session, code, name=None):
    from app.models.compliance_models import RegulatoryFramework

    row = RegulatoryFramework(code=code, name=name or code)
    db_session.add(row)
    db_session.flush()
    return row


def _control(db_session, framework_id, control_code, title=None):
    from app.models.compliance_models import ComplianceControl

    row = ComplianceControl(
        framework_id=framework_id, control_code=control_code, title=title or control_code
    )
    db_session.add(row)
    db_session.flush()
    return row


def _requirement(
    db_session,
    element_id,
    *,
    framework_id=None,
    control_id=None,
    title="Requirement",
    risk_if_not_met=None,
    requirement_type="regulatory",
):
    from app.models.compliance_models import ComplianceRequirement

    row = ComplianceRequirement(
        archimate_element_id=element_id,
        title=title,
        description=f"{title} description",
        requirement_type=requirement_type,
        framework_id=framework_id,
        control_id=control_id,
        risk_if_not_met=risk_if_not_met,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _gap(
    db_session,
    requirement_id,
    *,
    gap_type="missing_requirement",
    title="Gap",
    risk_level="high",
    likelihood=None,
    remediation_action=None,
    target_completion_date=None,
    status="open",
    estimated_cost=None,
):
    from app.models.compliance_models import ComplianceGap

    row = ComplianceGap(
        compliance_requirement_id=requirement_id,
        gap_type=gap_type,
        title=title,
        description=f"{title} description",
        risk_level=risk_level,
        likelihood=likelihood,
        remediation_action=remediation_action,
        target_completion_date=target_completion_date,
        status=status,
        estimated_cost=estimated_cost,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _user(db_session, org_id, *, email=None, enterprise_role=None):
    from app.models.user import Role, User

    admin_role = Role.query.filter_by(name="Administrator").first()
    if admin_role is None:
        Role.insert_roles()
        admin_role = Role.query.filter_by(name="Administrator").first()

    user = User(
        email=email or f"control-gaps-{uuid.uuid4().hex[:10]}@example.com",
        first_name="ControlGaps",
        last_name="Tester",
        organization_id=org_id,
        role=admin_role,
        is_org_admin=True,
        confirmed=True,
        enterprise_role=enterprise_role,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _org_a_scenario(db_session, make_org, label="control-gaps-org-a"):
    """app_a serving app_b, a GDPR requirement mirrored on app_b with two
    gaps, a SOC2 requirement on app_a with one gap, and a direct risk on
    app_a.
    """
    org_a = make_org(label)
    app_a = _element(db_session, org_a.id, "AppA")
    app_b = _element(db_session, org_a.id, "AppB")
    _relationship(db_session, org_a.id, app_a, app_b, type_="Serving")
    comp_a = _component(db_session, org_a.id, app_a.id, name="CompA")

    gdpr = _framework(db_session, "GDPR", name="General Data Protection Regulation")
    control = _control(db_session, gdpr.id, "Art-32")
    req_gdpr = _requirement(
        db_session,
        app_b.id,
        framework_id=gdpr.id,
        control_id=control.id,
        title="Encrypt data at rest",
        risk_if_not_met="critical",
    )
    gap1 = _gap(
        db_session, req_gdpr.id, title="Missing encryption", risk_level="critical",
        estimated_cost=15000,
    )
    gap2 = _gap(db_session, req_gdpr.id, title="No DPIA on file", risk_level="high")

    soc2 = _framework(db_session, "SOC2", name="SOC 2")
    req_soc2 = _requirement(
        db_session, app_a.id, framework_id=soc2.id, title="Access review cadence",
    )
    gap3 = _gap(db_session, req_soc2.id, title="Quarterly review overdue", risk_level="medium")

    _risk(db_session, org_a.id, app_a)
    db_session.commit()

    return org_a, app_a, app_b, comp_a, gdpr, soc2, [gap1, gap2, gap3]


def _service():
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    return IntelligenceQueryService


GAP_KEYS = {
    "gap_id",
    "element_id",
    "requirement_id",
    "requirement_title",
    "framework_code",
    "framework_name",
    "control_code",
    "gap_type",
    "title",
    "risk_level",
    "likelihood",
    "remediation_action",
    "target_completion_date",
    "status",
    "risk_if_not_met",
    "estimated_cost",
    "access_reason",
    "truth_class",
}

TAGS_KEYS = {
    "tags",
    "tags_text",
    "gdpr_compliant",
    "pii_data_processed",
    "data_classification",
    "requirements_text",
    "reason",
}


# --- (1) two-organisation: the answer lists every gap on the blast radius ----


def test_answer_lists_gaps_across_the_blast_radius_ordered_by_element(app, db_session, make_org):
    org_a, app_a, app_b, comp_a, gdpr, soc2, gaps = _org_a_scenario(db_session, make_org)

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org_a.id
        result = _service().risk_for_element(app_a.id)

    assert result["control_gaps"] is not None
    assert len(result["control_gaps"]) == 3
    codes = {row["framework_code"] for row in result["control_gaps"]}
    assert codes == {"GDPR", "SOC2"}
    element_ids = [row["element_id"] for row in result["control_gaps"]]
    assert element_ids == sorted(element_ids)
    assert result["control_gaps_reason"] is None
    assert result["framework"] is None


def test_framework_filter_narrows_to_the_named_framework(app, db_session, make_org):
    org_a, app_a, app_b, comp_a, gdpr, soc2, gaps = _org_a_scenario(db_session, make_org)

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org_a.id
        result = _service().risk_for_element(app_a.id, framework="GDPR")

    assert len(result["control_gaps"]) == 2
    assert all(row["framework_code"] == "GDPR" for row in result["control_gaps"])
    assert {row["element_id"] for row in result["control_gaps"]} == {app_b.id}
    assert result["framework"] == "GDPR"


# --- (2) a foreign requirement never appears, mutation-proved ---------------


def test_unrelated_tenant_never_appears_in_either_direction(app, db_session, make_org):
    org_a, app_a, app_b, comp_a, gdpr, soc2, gaps = _org_a_scenario(
        db_session, make_org, "control-gaps-iso-a"
    )

    org_b = make_org("control-gaps-iso-b")
    b_element = _element(db_session, org_b.id, "BOwn")
    b_framework = _framework(db_session, "B-FRAME")
    b_requirement = _requirement(db_session, b_element.id, framework_id=b_framework.id)
    b_gap = _gap(db_session, b_requirement.id, title="B's own gap")
    _risk(db_session, org_b.id, b_element, title="B's own risk")
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org_a.id
        a_result = _service().risk_for_element(app_a.id)

    a_gap_ids = {row["gap_id"] for row in a_result["control_gaps"]}
    assert b_gap.id not in a_gap_ids

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org_b.id
        b_result = _service().risk_for_element(b_element.id)

    assert len(b_result["control_gaps"]) == 1
    assert b_result["control_gaps"][0]["gap_id"] == b_gap.id
    b_result_gap_ids = {row["gap_id"] for row in b_result["control_gaps"]}
    assert b_result_gap_ids.isdisjoint({g.id for g in gaps})


def test_foreign_requirement_absence_is_mutation_proved(app, db_session, make_org, monkeypatch):
    """The compliance tables carry no tenant column of their own; the
    already-tenant-fenced identity map is the only fence a foreign
    requirement meets. Proved, not assumed: the SAME assertion holds on the
    real path and is shown to fail -- a genuine red run -- once the fence is
    disabled.
    """
    from app.modules.intelligence.services import query_service

    org_a = make_org("control-gaps-mut-a")
    org_b = make_org("control-gaps-mut-b")
    a = _element(db_session, org_a.id, "A")
    foreign = _element(db_session, org_b.id, "ForeignTarget")
    _relationship(db_session, org_a.id, a, foreign)
    _risk(db_session, org_a.id, a)
    framework = _framework(db_session, "MUT-FRAME")
    requirement = _requirement(db_session, foreign.id, framework_id=framework.id)
    gap = _gap(db_session, requirement.id, title="Foreign gap")
    db_session.commit()

    def _named_assertion(result):
        gap_ids = {row["gap_id"] for row in (result.get("control_gaps") or [])}
        assert gap.id not in gap_ids

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org_a.id
        real_result = _service().risk_for_element(a.id)
    _named_assertion(real_result)  # the fence holds on the real, unmodified path

    def _unfenced_resolve(element_ids, org_id):
        from app.extensions import db as _db
        from app.models import ArchiMateElement

        distinct_ids = sorted({eid for eid in element_ids if eid is not None})
        if not distinct_ids:
            return {}
        stmt = _db.select(
            ArchiMateElement.id, ArchiMateElement.name, ArchiMateElement.type,
            ArchiMateElement.layer,
        ).where(ArchiMateElement.id.in_(distinct_ids))  # organization_id predicate removed
        elements = {}
        for element_id, name, element_type, layer in _db.session.execute(stmt).all():
            if name is None:
                continue
            elements[str(element_id)] = {
                "id": element_id,
                "name": name,
                "type": element_type,
                "layer": str(layer) if layer is not None else None,
            }
        return elements

    monkeypatch.setattr(query_service, "_resolve_elements_batch", _unfenced_resolve)

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org_a.id
        mutated_result = _service().risk_for_element(a.id)

    # Record of the genuine red run this proves: with the fence disabled the
    # foreign gap DOES leak into the answer, so the same assertion now fails.
    with pytest.raises(AssertionError):
        _named_assertion(mutated_result)


# --- (3) a foreign element id is 404, and honestly None at service level ----


def test_cross_tenant_element_is_404_at_the_route(app, db_session, make_org, client, login_as):
    org_a = make_org("control-gaps-tenant-route-a")
    org_b = make_org("control-gaps-tenant-route-b")
    user_b = _user(db_session, org_b.id)
    a = _element(db_session, org_a.id, "A")
    _risk(db_session, org_a.id, a)
    db_session.commit()

    login_as(client, user_b)
    resp = client.get(f"/api/v1/intelligence/risk/{a.id}")
    assert resp.status_code == 404
    assert resp.get_json()["error"]["details"]["reason"] == "element_not_found"


def test_cross_tenant_element_service_level_blocks_are_none(app, db_session, make_org):
    org_a = make_org("control-gaps-tenant-service-a")
    org_b = make_org("control-gaps-tenant-service-b")
    a = _element(db_session, org_a.id, "A")
    _risk(db_session, org_a.id, a)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org_b.id
        result = _service().risk_for_element(a.id)

    assert result["risks"] == []
    assert result["reasons"] == ["element_not_found"]
    assert result["control_gaps"] is None
    assert result["control_gaps_reason"] is None
    assert result["framework"] is None
    assert result["compliance_tags"] is None


# --- (4) not recorded ---------------------------------------------------------


def test_no_requirement_anywhere_is_honest_absence(app, db_session, make_org):
    org = make_org("control-gaps-no-requirement")
    a = _element(db_session, org.id, "A")
    _risk(db_session, org.id, a)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = _service().risk_for_element(a.id)

    assert result["control_gaps"] is None
    assert result["control_gaps_reason"] == "no_compliance_mapping_recorded"


def test_requirement_with_no_gaps_is_empty_list_not_reason(app, db_session, make_org):
    org = make_org("control-gaps-req-no-gaps")
    a = _element(db_session, org.id, "A")
    _risk(db_session, org.id, a)
    framework = _framework(db_session, "F-NOGAPS")
    _requirement(db_session, a.id, framework_id=framework.id)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = _service().risk_for_element(a.id)

    assert result["control_gaps"] == []
    assert result["control_gaps_reason"] is None


# --- (5) the no-risk branch still runs the traversal -------------------------


def test_no_risk_branch_still_runs_traversal_for_control_gaps(app, db_session, make_org):
    org = make_org("control-gaps-no-risk-branch")
    a = _element(db_session, org.id, "A")
    b = _element(db_session, org.id, "B")
    _relationship(db_session, org.id, a, b)
    framework = _framework(db_session, "F-NORISK")
    requirement = _requirement(db_session, b.id, framework_id=framework.id)
    _gap(db_session, requirement.id)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = _service().risk_for_element(a.id)

    assert result["risks"] == []
    assert result["reasons"] == ["no_risk_recorded"]
    assert result["control_gaps"] is not None
    assert len(result["control_gaps"]) == 1
    assert result["elements"]  # non-empty: the one traversal populated it


# --- (6) an unknown framework code --------------------------------------------


def test_unknown_framework_code_raises_at_service(app, db_session, make_org):
    org = make_org("control-gaps-unknown-fw-service")
    a = _element(db_session, org.id, "A")
    _risk(db_session, org.id, a)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        with pytest.raises(ValueError):
            _service().risk_for_element(a.id, framework="NOPE-NOT-REAL")


def test_unknown_framework_code_is_400_at_route_and_names_no_known_code(
    app, db_session, make_org, client, login_as
):
    org = make_org("control-gaps-unknown-fw-route")
    user = _user(db_session, org.id)
    a = _element(db_session, org.id, "A")
    _risk(db_session, org.id, a)
    _framework(db_session, "GDPR")
    _framework(db_session, "SOC2")
    db_session.commit()

    login_as(client, user)
    resp = client.get(f"/api/v1/intelligence/risk/{a.id}?framework=NOPE-NOT-REAL")
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "INVALID_PARAMETER"
    body = resp.get_data(as_text=True)
    assert "GDPR" not in body
    assert "SOC2" not in body


def test_framework_param_over_fifty_chars_is_400(app, db_session, make_org, client, login_as):
    org = make_org("control-gaps-fw-toolong")
    user = _user(db_session, org.id)
    a = _element(db_session, org.id, "A")
    db_session.commit()

    login_as(client, user)
    resp = client.get(f"/api/v1/intelligence/risk/{a.id}?framework={'X' * 51}")
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "INVALID_PARAMETER"


# --- (7) the component's own recorded compliance tags -----------------------


def test_compliance_tags_parses_json_list(app, db_session, make_org):
    org = make_org("control-gaps-tags-json")
    a = _element(db_session, org.id, "A")
    _component(db_session, org.id, a.id, compliance_tags='["PCI-DSS"]')
    _risk(db_session, org.id, a)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = _service().risk_for_element(a.id)

    assert result["compliance_tags"]["tags"] == ["PCI-DSS"]
    assert result["compliance_tags"]["tags_text"] is None


def test_compliance_tags_unparseable_text_is_carried_not_guessed(app, db_session, make_org):
    org = make_org("control-gaps-tags-notjson")
    a = _element(db_session, org.id, "A")
    _component(db_session, org.id, a.id, compliance_tags="not json")
    _risk(db_session, org.id, a)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = _service().risk_for_element(a.id)

    assert result["compliance_tags"]["tags"] is None
    assert result["compliance_tags"]["tags_text"] == "not json"


def test_compliance_tags_all_text_columns_none_is_honest_absence(app, db_session, make_org):
    org = make_org("control-gaps-tags-none")
    a = _element(db_session, org.id, "A")
    _component(db_session, org.id, a.id)
    _risk(db_session, org.id, a)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = _service().risk_for_element(a.id)

    tags = result["compliance_tags"]
    assert tags["reason"] == "no_compliance_mapping_recorded"
    assert tags["tags"] is None
    assert tags["tags_text"] is None
    assert tags["data_classification"] is None
    assert tags["requirements_text"] is None
    # The two booleans carry a real column default and are not folded into
    # the reason -- disclosed as recorded, driven by the three text columns
    # only.
    assert tags["gdpr_compliant"] is False
    assert tags["pii_data_processed"] is False


def test_compliance_tags_non_component_element_is_no_application_component(
    app, db_session, make_org
):
    org = make_org("control-gaps-tags-nocomp")
    a = _element(db_session, org.id, "A", layer="business", type_="BusinessActor")
    _risk(db_session, org.id, a)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = _service().risk_for_element(a.id)

    assert result["compliance_tags"] == {
        "tags": None,
        "tags_text": None,
        "gdpr_compliant": None,
        "pii_data_processed": None,
        "data_classification": None,
        "requirements_text": None,
        "reason": "no_application_component",
    }


# --- (8) shape and batching ----------------------------------------------------


def test_gap_entry_has_the_exact_named_key_set(app, db_session, make_org):
    org = make_org("control-gaps-gap-shape")
    a = _element(db_session, org.id, "A")
    _risk(db_session, org.id, a)
    framework = _framework(db_session, "F-SHAPE")
    control = _control(db_session, framework.id, "CTRL-1")
    requirement = _requirement(db_session, a.id, framework_id=framework.id, control_id=control.id)
    _gap(db_session, requirement.id)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = _service().risk_for_element(a.id)

    assert len(result["control_gaps"]) == 1
    entry = result["control_gaps"][0]
    assert set(entry.keys()) == GAP_KEYS
    assert len(entry) == 18
    assert entry["truth_class"] == "authoritative_fact"
    assert entry["access_reason"] is None


def test_compliance_tags_has_the_exact_seven_key_set(app, db_session, make_org):
    org = make_org("control-gaps-tags-shape")
    a = _element(db_session, org.id, "A")
    _component(db_session, org.id, a.id, compliance_tags='["HIPAA"]')
    _risk(db_session, org.id, a)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = _service().risk_for_element(a.id)

    assert set(result["compliance_tags"].keys()) == TAGS_KEYS
    assert len(result["compliance_tags"]) == 7


class _ComplianceStatementCounter:
    """Records every SELECT touching a compliance table this task reads."""

    def __init__(self):
        self.statements = []

    def __call__(self, conn, cursor, statement, parameters, context, executemany):
        lowered = statement.lower()
        if any(
            table in lowered
            for table in ("compliance_requirements", "compliance_gaps", "regulatory_frameworks")
        ):
            self.statements.append(statement)


@pytest.fixture
def compliance_counter(app):
    from app.extensions import db

    counter = _ComplianceStatementCounter()
    event.listen(db.engine, "before_cursor_execute", counter)
    try:
        yield counter
    finally:
        event.remove(db.engine, "before_cursor_execute", counter)


def test_control_gap_selects_are_constant_for_one_gap_and_twenty(
    app, db_session, make_org, compliance_counter
):
    org = make_org("control-gaps-select-count")
    a = _element(db_session, org.id, "A")
    _risk(db_session, org.id, a)
    framework = _framework(db_session, "F-COUNT")
    requirement = _requirement(db_session, a.id, framework_id=framework.id)
    _gap(db_session, requirement.id)
    db_session.commit()

    compliance_counter.statements.clear()
    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        one = _service().risk_for_element(a.id)
    one_count = len(compliance_counter.statements)
    assert len(one["control_gaps"]) == 1

    for _ in range(19):
        _gap(db_session, requirement.id)
    db_session.commit()

    compliance_counter.statements.clear()
    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        many = _service().risk_for_element(a.id)
    many_count = len(compliance_counter.statements)
    assert len(many["control_gaps"]) == 20

    assert one_count == many_count
    assert one_count <= 4


def test_risk_payloads_identical_with_and_without_requirements(app, db_session, make_org):
    org = make_org("control-gaps-risk-identical")
    a = _element(db_session, org.id, "A")
    _risk(db_session, org.id, a, title="Some risk")
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        before = _service().risk_for_element(a.id)

    framework = _framework(db_session, "F-IDENTICAL")
    requirement = _requirement(db_session, a.id, framework_id=framework.id)
    _gap(db_session, requirement.id)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        after = _service().risk_for_element(a.id)

    assert before["risks"] == after["risks"]
    assert before["reasons"] == after["reasons"]
    assert before["elements"] == after["elements"]
    assert after["control_gaps"] is not None  # the second run has something new


# --- (11) fabrication ----------------------------------------------------------


def test_fabrication_all_unrecorded_blocks_are_null_not_defaulted(app, db_session, make_org):
    org = make_org("control-gaps-fabrication")
    a = _element(db_session, org.id, "A", layer="business", type_="BusinessActor")
    _risk(db_session, org.id, a)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = _service().risk_for_element(a.id)

    assert result["control_gaps"] is None
    assert result["control_gaps_reason"] == "no_compliance_mapping_recorded"
    tags = result["compliance_tags"]
    assert tags["reason"] == "no_application_component"
    for key, value in tags.items():
        if key == "reason":
            continue
        assert value is None, (key, value)

    body = json.dumps(result)
    assert '"estimated_cost": 0' not in body
    assert '"gap_id"' not in body  # control_gaps is None: no gap fabricated
    assert result["risks"] == []


def test_fabrication_reason_is_driven_by_text_columns_only_not_the_booleans(
    app, db_session, make_org
):
    """The two boolean columns carry a real column default (False) and are
    disclosed as recorded -- setting them to True changes nothing about
    which reason fires, proving the reason is driven by the three text
    columns alone, never by treating an unset boolean as absence."""
    org = make_org("control-gaps-fabrication-bool")
    a = _element(db_session, org.id, "A")
    _component(db_session, org.id, a.id, gdpr_compliant=True, pii_data_processed=True)
    _risk(db_session, org.id, a)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = _service().risk_for_element(a.id)

    tags = result["compliance_tags"]
    assert tags["reason"] == "no_compliance_mapping_recorded"
    assert tags["gdpr_compliant"] is True
    assert tags["pii_data_processed"] is True
    assert tags["tags"] is None
    assert tags["tags_text"] is None
    assert tags["data_classification"] is None
    assert tags["requirements_text"] is None


def test_fabrication_estimated_cost_is_never_zero_beside_a_null(app, db_session, make_org):
    org = make_org("control-gaps-fabrication-cost")
    a = _element(db_session, org.id, "A")
    _risk(db_session, org.id, a)
    framework = _framework(db_session, "F-COST")
    requirement = _requirement(db_session, a.id, framework_id=framework.id)
    _gap(db_session, requirement.id, title="No cost recorded")  # estimated_cost left unset
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = _service().risk_for_element(a.id)

    assert result["control_gaps"][0]["estimated_cost"] is None
    assert '"estimated_cost": 0' not in json.dumps(result)


def test_fabrication_no_default_operator_on_the_read_path(app):
    """Companion, unit-level pin for the ``git diff ... | grep`` ratchet run
    alongside this suite: no field on a gap or tags entry is ever computed
    via ``or 0``/``or 1``/``or 3``/``max(x, 1)`` inside this method's own
    source.
    """
    import inspect
    import re

    from app.modules.intelligence.services import query_service

    source = inspect.getsource(query_service.IntelligenceQueryService.risk_for_element)
    assert not re.search(r"or 0\b|or 1\b|or 3\b|max\(.*, 1\)", source)


# --- (12) route and redaction --------------------------------------------------


def test_route_framework_filter_and_redaction(app, db_session, make_org, client, login_as):
    org = make_org("control-gaps-route-filter")
    user_no_auth = _user(db_session, org.id, enterprise_role="business_architect")
    user_cto = _user(db_session, org.id, enterprise_role="cto")
    a = _element(db_session, org.id, "A")
    b = _element(db_session, org.id, "B")
    _relationship(db_session, org.id, a, b)
    _risk(db_session, org.id, a)
    gdpr = _framework(db_session, "GDPR")
    requirement = _requirement(db_session, b.id, framework_id=gdpr.id)
    _gap(db_session, requirement.id, title="Encryption gap", estimated_cost=1000)
    db_session.commit()

    login_as(client, user_no_auth)
    resp = client.get(f"/api/v1/intelligence/risk/{a.id}?framework=GDPR")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["framework"] == "GDPR"
    assert len(data["control_gaps"]) == 1
    assert data["control_gaps"][0]["framework_code"] == "GDPR"
    assert data["control_gaps"][0]["estimated_cost"] is None
    assert data["control_gaps"][0]["access_reason"] == "financial_data_restricted"

    login_as(client, user_cto)
    resp_cto = client.get(f"/api/v1/intelligence/risk/{a.id}?framework=GDPR")
    assert resp_cto.status_code == 200
    data_cto = resp_cto.get_json()["data"]
    assert data_cto["control_gaps"][0]["estimated_cost"] == 1000.0
    assert data_cto["control_gaps"][0]["access_reason"] is None
