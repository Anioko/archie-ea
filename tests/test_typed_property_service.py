"""Typed property writes must coerce, scope and refuse invalid values."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _seed_templates():
    from app.commands.seed_viewpoints import seed_property_templates

    seed_property_templates()


def _make_user(db_session, org_id, email_prefix):
    from app.models.user import Role, User

    Role.insert_roles()
    architect_role = Role.query.filter_by(name="Architect").one()
    user = User(
        email=f"{email_prefix}@example.com",
        first_name="Typed",
        last_name="Writer",
        organization_id=org_id,
        enterprise_role="enterprise_architect",
        confirmed=True,
    )
    user.role = architect_role
    user.password = "TestPass!2026"
    db_session.add(user)
    db_session.flush()
    return user


def _make_solution(db_session, org_id, owner_id, name="Typed properties solution"):
    from app.models.solution_models import Solution

    solution = Solution(name=name, organization_id=org_id, created_by_id=owner_id)
    db_session.add(solution)
    db_session.flush()
    return solution


def _make_proposal(db_session, solution_id, org_id, archimate_type="ApplicationInterface"):
    from app.models.solution_blueprint_proposal import SolutionBlueprintProposal

    proposal = SolutionBlueprintProposal(
        solution_id=solution_id,
        organization_id=org_id,
        archimate_type=archimate_type,
        name="Payments API",
        status="accepted",
    )
    db_session.add(proposal)
    db_session.flush()
    return proposal


def test_set_element_property_stores_number_unit_and_source(db_session, make_org):
    from app.models.archimate_core import ArchiMateElement
    from app.modules.architecture_assistant.property_service import PropertyService

    _seed_templates()
    org = make_org("typed-prop-element")
    element = ArchiMateElement(
        name="Customer API",
        type="ApplicationInterface",
        layer="application",
        organization_id=org.id,
    )
    db_session.add(element)
    db_session.flush()

    entry = PropertyService().set_element_property(element, "rate_limit", "1200 req/min")
    db_session.flush()

    assert entry == {"value": 1200, "unit": "req/min", "source": "user"}
    assert element.acm_properties["rate_limit"] == entry


def test_set_element_property_refuses_unparseable_numeric_value(db_session, make_org):
    from app.models.archimate_core import ArchiMateElement
    from app.modules.architecture_assistant.property_service import PropertyService, PropertyValidationError

    _seed_templates()
    org = make_org("typed-prop-refusal")
    element = ArchiMateElement(
        name="Customer API",
        type="ApplicationInterface",
        layer="application",
        organization_id=org.id,
        acm_properties={"rate_limit": {"value": 900, "unit": "req/min", "source": "user"}},
    )
    db_session.add(element)
    db_session.flush()

    with pytest.raises(PropertyValidationError, match="Enter a number"):
        PropertyService().set_element_property(element, "rate_limit", "not a number")

    assert element.acm_properties["rate_limit"]["value"] == 900


def test_update_proposal_properties_refuses_invalid_numeric_text(client, db_session, make_org, login_as):
    _seed_templates()
    org = make_org("typed-prop-route")
    owner = _make_user(db_session, org.id, "typed-route-owner")
    solution = _make_solution(db_session, org.id, owner.id)
    proposal = _make_proposal(db_session, solution.id, org.id)
    proposal.acm_properties = {"rate_limit": {"value": 800, "unit": "req/min", "source": "user"}}
    db_session.flush()

    login_as(client, owner)
    response = client.patch(
        f"/architecture-journey/{solution.id}/proposals/{proposal.id}/properties",
        json={"properties": {"rate_limit": "plain text"}},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Enter a number for this property."

    db_session.expire_all()
    reloaded = db_session.get(type(proposal), proposal.id)
    assert reloaded.acm_properties["rate_limit"]["value"] == 800


def test_update_proposal_properties_is_tenant_scoped(client, db_session, make_org, login_as):
    _seed_templates()
    org_a = make_org("typed-prop-a")
    org_b = make_org("typed-prop-b")
    owner_a = _make_user(db_session, org_a.id, "typed-owner-a")
    owner_b = _make_user(db_session, org_b.id, "typed-owner-b")
    solution_b = _make_solution(db_session, org_b.id, owner_b.id, name="Foreign solution")
    proposal_b = _make_proposal(db_session, solution_b.id, org_b.id)
    proposal_b.acm_properties = {"rate_limit": {"value": 700, "unit": "req/min", "source": "user"}}
    db_session.flush()

    login_as(client, owner_a)
    response = client.patch(
        f"/architecture-journey/{solution_b.id}/proposals/{proposal_b.id}/properties",
        json={"properties": {"rate_limit": "1300 req/min"}},
    )

    assert response.status_code == 403

    db_session.expire_all()
    reloaded = db_session.get(type(proposal_b), proposal_b.id)
    assert reloaded.acm_properties["rate_limit"]["value"] == 700


def test_update_element_route_persists_typed_number_and_unit(client, db_session, make_org, login_as):
    from app.models.archimate_core import ArchiMateElement
    from app.models.solution_archimate_element import SolutionArchiMateElement

    _seed_templates()
    org = make_org("typed-prop-element-route")
    owner = _make_user(db_session, org.id, "typed-element-owner")
    solution = _make_solution(db_session, org.id, owner.id, name="Element route solution")
    element = ArchiMateElement(
        name="Payments Service",
        type="ApplicationService",
        layer="application",
        organization_id=org.id,
        acm_properties={"availability_target": {"value": 99.5, "unit": "%", "source": "user"}},
    )
    db_session.add(element)
    db_session.flush()
    db_session.add(SolutionArchiMateElement(solution_id=solution.id, element_id=element.id))
    db_session.flush()

    login_as(client, owner)
    response = client.patch(
        f"/architecture-journey/{solution.id}/element/{element.id}",
        json={"acm_properties": {"availability_target": "99.9%"}},
    )

    assert response.status_code == 200
    db_session.expire_all()
    reloaded = db_session.get(ArchiMateElement, element.id)
    assert reloaded.acm_properties["availability_target"] == {
        "value": 99.9,
        "unit": "%",
        "source": "user",
    }
