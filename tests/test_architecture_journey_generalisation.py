"""Product contracts for the purpose-led Architecture Journey."""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture
def ba_user(db_session, make_org):
    from app.models.user import ROLE_BUSINESS_ARCHITECT, User

    org = make_org("journey-ba")
    user = User(
        email=f"journey-ba-{uuid.uuid4().hex[:10]}@example.test",
        first_name="Bea",
        last_name="Archer",
        confirmed=True,
        organization_id=org.id,
        enterprise_role=ROLE_BUSINESS_ARCHITECT,
    )
    user.password = "test-password-not-secret"
    db_session.add(user)
    db_session.flush()
    return user


def test_business_architecture_landing_is_permanently_discontinued(app, ba_user, login_as):
    client = app.test_client()
    login_as(client, ba_user)

    response = client.get("/business-architecture/", follow_redirects=False)

    assert response.status_code == 301
    assert response.headers["Location"].endswith(
        "/architecture-journey/?intent=business-transformation"
    )


def test_architecture_journey_has_an_identity_independent_of_a_solution(
    db_session, make_org, ba_user
):
    from app.models.architecture_journey import ArchitectureJourney

    journey = ArchitectureJourney(
        organization_id=ba_user.organization_id,
        owner_id=ba_user.id,
        title="Reimagine customer fulfilment",
        intent="business_transformation",
        selected_layers=["motivation", "business", "data"],
        evidence_manifest=[{"kind": "document", "name": "Operating model.pdf"}],
        selected_deliverables=["capability_map", "business_architecture_document"],
        outcome_type="architecture_only",
    )
    db_session.add(journey)
    db_session.flush()

    assert journey.id is not None
    assert journey.solution_id is None
    assert journey.resume_path == f"/architecture-journey/work/{journey.id}"


def test_hub_visibly_frames_non_solution_outcomes(app, ba_user, login_as):
    client = app.test_client()
    login_as(client, ba_user)

    response = client.get("/architecture-journey/?intent=business-transformation")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert body.count("<h1") == 1
    assert "Purpose before artefacts" in body
    assert "No change recommended" in body
    assert "A solution is one possible outcome" in body
    assert "Business Architecture" not in body
    assert "layers.includes" not in body


def test_start_creates_journey_without_creating_solution(app, ba_user, login_as, db_session):
    from app.models.architecture_journey import ArchitectureJourney
    from app.models.solution_models import Solution

    client = app.test_client()
    login_as(client, ba_user)
    before_solutions = Solution.query.filter_by(created_by_id=ba_user.id).count()

    response = client.post(
        "/architecture-journey/start-architecture",
        json={
            "title": "Redesign customer fulfilment",
            "intent": "business_transformation",
            "selected_layers": ["motivation", "business", "data"],
            "selected_deliverables": ["capability_map", "value_stream"],
            "outcome_type": "no_change_recommended",
        },
    )

    assert response.status_code == 201
    journey_id = response.get_json()["data"]["journey_id"]
    journey = ArchitectureJourney.query.filter_by(id=journey_id).one()
    assert journey.owner_id == ba_user.id
    assert journey.solution_id is None
    assert Solution.query.filter_by(created_by_id=ba_user.id).count() == before_solutions


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ({"current_stage": "invent"}, "valid journey stage"),
        ({"selected_deliverables": ["invented_report"]}, "valid journey deliverables"),
        ({"evidence_manifest": "not-a-list"}, "Evidence must be a list"),
        ({"journey_state": ["not-an-object"]}, "Journey state must be an object"),
    ],
)
def test_state_patch_rejects_invalid_or_unbounded_shape(
    app, ba_user, login_as, db_session, patch, message
):
    from app.models.architecture_journey import ArchitectureJourney

    journey = ArchitectureJourney(
        organization_id=ba_user.organization_id,
        owner_id=ba_user.id,
        title="Governed journey",
        intent="architecture_assessment",
        selected_layers=["business"],
    )
    db_session.add(journey)
    db_session.flush()
    client = app.test_client()
    login_as(client, ba_user)

    response = client.patch(f"/architecture-journey/work/{journey.id}/state", json=patch)

    assert response.status_code == 400
    assert message in response.get_json()["error"]


def test_non_owner_cannot_open_or_patch_journey(app, ba_user, login_as, db_session, make_org):
    from app.models.architecture_journey import ArchitectureJourney
    from app.models.user import ROLE_BUSINESS_ARCHITECT, User

    journey = ArchitectureJourney(
        organization_id=ba_user.organization_id,
        owner_id=ba_user.id,
        title="Owner-only journey",
        intent="operating_model",
        selected_layers=["business"],
    )
    db_session.add(journey)
    db_session.flush()
    other_org = make_org("journey-other")
    other = User(
        email=f"other-{uuid.uuid4().hex[:10]}@example.test",
        first_name="Other",
        last_name="Architect",
        confirmed=True,
        organization_id=other_org.id,
        enterprise_role=ROLE_BUSINESS_ARCHITECT,
    )
    other.password = "test-password-not-secret"
    db_session.add(other)
    db_session.flush()
    client = app.test_client()
    login_as(client, other)

    assert client.get(f"/architecture-journey/work/{journey.id}").status_code == 404
    assert client.patch(
        f"/architecture-journey/work/{journey.id}/state", json={"current_stage": "discover"}
    ).status_code == 404


def test_deliverable_tool_links_are_built_from_registered_endpoints(app, ba_user, login_as):
    from app.modules.solutions_strategic.v2.routes.journey_v2_routes import (
        DELIVERABLE_TOOL_ENDPOINTS,
    )

    client = app.test_client()
    login_as(client, ba_user)
    response = client.get("/architecture-journey/")
    assert response.status_code == 200
    with app.test_request_context("/"):
        from flask import url_for

        for endpoint in DELIVERABLE_TOOL_ENDPOINTS.values():
            if endpoint in app.view_functions:
                assert url_for(endpoint).startswith("/")


def test_new_journey_table_is_registered_for_create_all_and_schema_drift(app):
    from app import db
    from app.models.architecture_journey import ArchitectureJourney
    from sqlalchemy import inspect

    assert ArchitectureJourney.__table__.name in db.metadata.tables
    with app.app_context():
        columns = {column["name"] for column in inspect(db.engine).get_columns("architecture_journeys")}
    assert {
        "organization_id", "owner_id", "intent", "selected_layers",
        "evidence_manifest", "selected_deliverables", "outcome_type",
        "journey_state", "current_stage", "solution_id", "programme_id",
    } <= columns


def test_same_tenant_administrator_can_resume_owned_journey(
    app, ba_user, login_as, db_session
):
    from app.models.architecture_journey import ArchitectureJourney
    from app.models.user import ROLE_PLATFORM_ADMIN, Permission, Role, User

    admin_role = Role.query.filter_by(name="Administrator").first()
    if admin_role is None:
        admin_role = Role(name="Administrator", permissions=Permission.ADMINISTER, index="admin")
        db_session.add(admin_role)
        db_session.flush()
    else:
        admin_role.permissions = Permission.ADMINISTER
    admin = User(
        email=f"journey-admin-{uuid.uuid4().hex[:10]}@example.test",
        first_name="Admin",
        last_name="Architect",
        confirmed=True,
        organization_id=ba_user.organization_id,
        enterprise_role=ROLE_PLATFORM_ADMIN,
        role_id=admin_role.id,
        is_platform_admin=True,
    )
    admin.password = "test-password-not-secret"
    journey = ArchitectureJourney(
        organization_id=ba_user.organization_id,
        owner_id=ba_user.id,
        title="Governed shared journey",
        intent="risk_and_compliance",
        selected_layers=["governance"],
    )
    db_session.add_all([admin, journey])
    db_session.flush()
    client = app.test_client()
    login_as(client, admin)

    assert client.get(f"/architecture-journey/work/{journey.id}").status_code == 200
