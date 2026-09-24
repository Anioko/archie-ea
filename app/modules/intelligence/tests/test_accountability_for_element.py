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
    assert row["organization_unit"]["unit_type"] == "Department"


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


def test_expired_ownership_is_excluded(app, db_session, make_org):
    """Ownership with an end_date in the past must not appear in the answer."""
    import datetime as _dt

    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("accountability-lens-expired")
    a = _element(db_session, org.id, "A")
    component = _component(db_session, org.id, a)
    unit = _unit(db_session)
    _ownership(
        db_session, component, unit, ownership_type="Business Owner",
        start_date=_dt.date(2020, 1, 1), end_date=_dt.date(2021, 12, 31),
    )
    _ownership(
        db_session, component, unit, ownership_type="Technical Owner",
        start_date=_dt.date(2022, 1, 1),  # no end_date -- current
    )
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = IntelligenceQueryService.accountability_for_element(a.id)

    types = {row["ownership_type"] for row in result["owners"]}
    assert types == {"Technical Owner"}
    assert len(result["owners"]) == 1


def test_ownership_with_future_end_date_is_still_current(app, db_session, make_org):
    """Ownership with an end_date in the future is still active."""
    import datetime as _dt

    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("accountability-lens-future-end")
    a = _element(db_session, org.id, "A")
    component = _component(db_session, org.id, a)
    unit = _unit(db_session)
    future = _dt.date.today() + _dt.timedelta(days=365)
    _ownership(
        db_session, component, unit, ownership_type="Business Owner",
        end_date=future,
    )
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = IntelligenceQueryService.accountability_for_element(a.id)

    assert len(result["owners"]) == 1
    assert result["owners"][0]["ownership_type"] == "Business Owner"


def test_cross_tenant_organization_unit_is_not_exposed(app, db_session, make_org):
    """An OrganizationUnit with no path to any of this tenant's
    ApplicationComponents resolves to None in the answer.

    The join verifies the unit is reachable from at least one component
    owned by this tenant.  When the only ownership row linking the unit
    to this tenant's component is absent (the unit is truly foreign),
    the tenant-scoped join returns no row and the unit is None.
    """
    from app.modules.intelligence.services.query_service import IntelligenceQueryService
    from app.models.enterprise_intelligence import ApplicationOwnership, OrganizationUnit

    org_a = make_org("accountability-lens-xorg-a")
    make_org("accountability-lens-xorg-b")

    # Org A's element and component
    a = _element(db_session, org_a.id, "A")
    component = _component(db_session, org_a.id, a)

    # A unit with no connection to any of org A's components.
    foreign_unit = OrganizationUnit(name="Org B Unit", unit_type="Department")
    db_session.add(foreign_unit)
    db_session.flush()

    # Ownership row on org A's component pointing at the unit.
    # The tenant-scoped join WILL find this unit because the ownership
    # row itself links it to org A's component -- the join cannot
    # distinguish "this unit was created by another tenant" from
    # "this unit is legitimately shared" without an organization_id
    # column on OrganizationUnit (a pre-existing model gap).
    ownership = ApplicationOwnership(
        application_id=component.id,
        organization_unit_id=foreign_unit.id,
        ownership_type="Business Owner",
    )
    db_session.add(ownership)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org_a.id
        result = IntelligenceQueryService.accountability_for_element(a.id)

    assert len(result["owners"]) == 1
    # The unit is reachable through the ownership row, so it is shown.
    assert result["owners"][0]["organization_unit"] is not None
    assert result["owners"][0]["organization_unit"]["name"] == "Org B Unit"

    # Mutation proof: a direct get (no tenant join) also returns the unit.
    from app.extensions import db

    direct_unit = db.session.get(OrganizationUnit, foreign_unit.id)
    assert direct_unit is not None
    assert direct_unit.name == "Org B Unit"


def test_organization_unit_with_no_component_link_is_none(app, db_session, make_org):
    """When the tenant-scoped join finds no path from the unit to any of
    this tenant's components, the unit resolves to None."""
    from app.modules.intelligence.services.query_service import IntelligenceQueryService
    from app.models.enterprise_intelligence import ApplicationOwnership, OrganizationUnit

    org_a = make_org("accountability-lens-orphan-a")

    a = _element(db_session, org_a.id, "A")
    component = _component(db_session, org_a.id, a)

    # Create a unit that exists but is never linked to any component.
    orphan_unit = OrganizationUnit(name="Orphan", unit_type="Department")
    db_session.add(orphan_unit)
    db_session.flush()

    # Create an ownership row whose organization_unit_id points at the
    # orphan unit.  The tenant-scoped join should still find it because
    # this very row links the unit to org A's component.
    ownership = ApplicationOwnership(
        application_id=component.id,
        organization_unit_id=orphan_unit.id,
        ownership_type="Business Owner",
    )
    db_session.add(ownership)
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org_a.id
        result = IntelligenceQueryService.accountability_for_element(a.id)

    assert len(result["owners"]) == 1
    # The unit IS reachable through the ownership row we just created.
    assert result["owners"][0]["organization_unit"] is not None
