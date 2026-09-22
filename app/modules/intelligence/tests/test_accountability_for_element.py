"""Tests for ``IntelligenceQueryService.accountability_for_element`` (L4):
resolves an element to its ApplicationComponent (reusing L3's own
resolution), then lists ApplicationOwnership rows for it. No blast-radius
traversal -- this lens is a pure ownership lookup. capacity_not_available
must be present in every response's reasons, success included.

Fixtures (app, db_session, make_org) are discovered via
app/modules/intelligence/tests/conftest.py's own import of tests.conftest,
same pattern as test_query_service.py. No import needed here.
"""

from __future__ import annotations


def _element(db_session, org_id, name, layer="application"):
    from app.models import ArchiMateElement

    el = ArchiMateElement(name=name, type="ApplicationComponent", layer=layer, organization_id=org_id)
    db_session.add(el)
    db_session.flush()
    return el


def _component(db_session, org_id, element, name="A App"):
    from app.models.application_portfolio import ApplicationComponent

    component = ApplicationComponent(name=name, organization_id=org_id, archimate_element_id=element.id)
    db_session.add(component)
    db_session.flush()
    return component


def _unit(db_session, *, name="Finance", unit_type="Department", head_of_unit=None):
    from app.models.enterprise_intelligence import OrganizationUnit

    unit = OrganizationUnit(name=name, unit_type=unit_type, head_of_unit=head_of_unit)
    db_session.add(unit)
    db_session.flush()
    return unit


def _ownership(db_session, component, unit, *, ownership_type="Business Owner",
               ownership_percentage=100, primary_contact=None, contact_email=None,
               start_date=None, end_date=None):
    # organization_unit_id is NOT NULL on this model -- every real ownership
    # row names a unit. The "no unit" case tested below is an orphaned FK
    # (the unit row was later deleted), not a row created without one.
    from app.models.enterprise_intelligence import ApplicationOwnership

    ownership = ApplicationOwnership(
        application_id=component.id,
        organization_unit_id=unit.id,
        ownership_type=ownership_type,
        ownership_percentage=ownership_percentage,
        primary_contact=primary_contact,
        contact_email=contact_email,
        start_date=start_date,
        end_date=end_date,
    )
    db_session.add(ownership)
    db_session.flush()
    return ownership


def test_element_that_is_not_an_application_component_returns_honest_reason(app, db_session, make_org):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("accountability-lens-not-app")
    a = _element(db_session, org.id, "A", layer="business")
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = IntelligenceQueryService.accountability_for_element(a.id)

    assert result["owners"] == []
    assert result["capacity_not_available"] is True
    assert "no_application_component" in result["reasons"]
    assert "capacity_not_available" in result["reasons"]


def test_unknown_element_returns_element_not_found_reason(app, db_session, make_org):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("accountability-lens-unknown")
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = IntelligenceQueryService.accountability_for_element(999999999)

    assert result["owners"] == []
    assert "element_not_found" in result["reasons"]
    assert "capacity_not_available" in result["reasons"]


def test_no_tenant_context_returns_honest_reason(app, db_session, make_org):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("accountability-lens-no-ctx")
    a = _element(db_session, org.id, "A")
    _component(db_session, org.id, a)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = None
        result = IntelligenceQueryService.accountability_for_element(a.id)

    assert result["owners"] == []
    assert "no_tenant_context" in result["reasons"]
    assert "capacity_not_available" in result["reasons"]


def test_component_with_no_ownership_records_returns_honest_empty(app, db_session, make_org):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("accountability-lens-empty")
    a = _element(db_session, org.id, "A")
    _component(db_session, org.id, a)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = IntelligenceQueryService.accountability_for_element(a.id)

    assert result["owners"] == []
    assert result["reasons"] == ["no_ownership_records", "capacity_not_available"]


def test_owner_with_organization_unit_renders_honestly(app, db_session, make_org):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("accountability-lens-owner")
    a = _element(db_session, org.id, "A")
    component = _component(db_session, org.id, a)
    unit = _unit(db_session, name="Finance", head_of_unit="Pat Head")
    _ownership(
        db_session, component, unit=unit, ownership_type="Business Owner",
        primary_contact="Jordan Owner", contact_email="jordan@example.com",
    )
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = IntelligenceQueryService.accountability_for_element(a.id)

    assert "capacity_not_available" in result["reasons"]
    assert len(result["owners"]) == 1
    row = result["owners"][0]
    assert row["ownership_type"] == "Business Owner"
    assert row["primary_contact"] == "Jordan Owner"
    assert row["organization_unit"]["name"] == "Finance"
    assert row["organization_unit"]["head_of_unit"] == "Pat Head"


def test_capacity_not_available_is_present_even_on_a_successful_answer(app, db_session, make_org):
    """Pins the lens's own defining honesty rule: capacity_not_available is
    not an error condition -- it must appear alongside a real, populated
    owners list too, since the capacity half of the question genuinely has
    no data source anywhere in this codebase."""
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("accountability-lens-capacity-always")
    a = _element(db_session, org.id, "A")
    component = _component(db_session, org.id, a)
    unit = _unit(db_session)
    _ownership(db_session, component, unit)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = IntelligenceQueryService.accountability_for_element(a.id)

    assert len(result["owners"]) == 1
    assert result["capacity_not_available"] is True
    assert "capacity_not_available" in result["reasons"]


def test_multiple_owners_on_one_component_each_get_their_own_row(app, db_session, make_org):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("accountability-lens-multi")
    a = _element(db_session, org.id, "A")
    component = _component(db_session, org.id, a)
    unit = _unit(db_session)
    _ownership(db_session, component, unit, ownership_type="Business Owner")
    _ownership(db_session, component, unit, ownership_type="Technical Owner")
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = IntelligenceQueryService.accountability_for_element(a.id)

    types = {row["ownership_type"] for row in result["owners"]}
    assert types == {"Business Owner", "Technical Owner"}


def test_expired_ownership_row_is_excluded(app, db_session, make_org):
    """A row whose end_date has already passed is not current ownership --
    it must not render as the accountable owner."""
    from datetime import date, timedelta

    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("accountability-lens-expired")
    a = _element(db_session, org.id, "A")
    component = _component(db_session, org.id, a)
    unit = _unit(db_session, name="Legacy Unit")
    _ownership(
        db_session, component, unit=unit, ownership_type="Business Owner",
        end_date=date.today() - timedelta(days=1),
    )
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = IntelligenceQueryService.accountability_for_element(a.id)

    assert result["owners"] == []
    assert result["reasons"] == ["no_ownership_records", "capacity_not_available"]


def test_ownership_row_with_no_end_date_or_future_end_date_is_current(app, db_session, make_org):
    from datetime import date, timedelta

    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("accountability-lens-current")
    a = _element(db_session, org.id, "A")
    component = _component(db_session, org.id, a)
    unit = _unit(db_session, name="Active Unit")
    _ownership(db_session, component, unit=unit, ownership_type="Business Owner")
    _ownership(
        db_session, component, unit=unit, ownership_type="Technical Owner",
        end_date=date.today() + timedelta(days=30),
    )
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = IntelligenceQueryService.accountability_for_element(a.id)

    end_dates = {row["ownership_type"]: row["end_date"] for row in result["owners"]}
    assert end_dates == {
        "Business Owner": None,
        "Technical Owner": (date.today() + timedelta(days=30)).isoformat(),
    }


def test_unit_hidden_when_component_tenant_check_fails(app, db_session, make_org, monkeypatch):
    """SEC-09 belt-and-braces companion to
    test_query_service.py::test_sec09_tenant_check_blocks_real_cross_tenant_resolution:
    accountability_for_element must not read OrganizationUnit off an
    ownership row's application_id alone -- it re-checks the resolved
    component's own organization_id against the caller's tenant first, the
    same assertion _resolve_owners_batch already applies before it will
    trust an owner/unit chain.

    Positive control first: an ordinary, unpatched request for org B's own
    element returns org B's own unit. Then current_org_id() (what the new
    assertion reads) is made to diverge from g.current_org_id (what the ORM
    tenant filter reads) -- the same drift the precedent test above
    constructs, the only way to reach the assertion with real, unmodified
    resolution logic, since both sources read the same value in any single
    live request today.
    """
    from app.modules.intelligence.services import query_service
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org_a = make_org("accountability-lens-tenancy-a")
    org_b = make_org("accountability-lens-tenancy-b")

    b_element = _element(db_session, org_b.id, "B App")
    b_component = _component(db_session, org_b.id, b_element, name="B App Component")
    b_unit = _unit(db_session, name="OrgB-Finance", head_of_unit="Blair Head")
    _ownership(db_session, b_component, unit=b_unit, ownership_type="Business Owner")
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org_b.id
        control = IntelligenceQueryService.accountability_for_element(b_element.id)

    assert len(control["owners"]) == 1
    assert control["owners"][0]["organization_unit"]["name"] == "OrgB-Finance"

    monkeypatch.setattr(query_service, "current_org_id", lambda: org_a.id)
    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org_b.id
        leaked = IntelligenceQueryService.accountability_for_element(b_element.id)

    assert len(leaked["owners"]) == 1
    assert leaked["owners"][0]["organization_unit"] is None
    assert "OrgB-Finance" not in str(leaked)
    assert "Blair Head" not in str(leaked)


def test_no_second_element_resolution_implementation(app, db_session, make_org):
    """The resolution step must be portfolio_component_for_element's own
    logic reused, not a second implementation -- pinned by checking both
    methods agree on the same real/absent-component verdict for the same
    element, the same regression guard L5 uses for cross_layer_impact
    reuse."""
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("accountability-lens-reuse")
    a = _element(db_session, org.id, "A")
    component = _component(db_session, org.id, a)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        direct = IntelligenceQueryService.portfolio_component_for_element(a.id)
        accountability = IntelligenceQueryService.accountability_for_element(a.id)

    assert direct["application_component_id"] == component.id
    # accountability_for_element resolves to the same component and returns
    # an honest-empty owners list (no ownership rows seeded), not an error.
    assert accountability["owners"] == []
    assert accountability["reasons"] == ["no_ownership_records", "capacity_not_available"]
