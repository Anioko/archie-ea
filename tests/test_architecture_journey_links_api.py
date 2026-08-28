"""Write paths for journey edges: linking records, and adding people.

The journey home counts participants, decisions, risks and governance. Without a
way to create those edges the counts are permanently zero and the screen is
decorative -- which is a worse failure than showing nothing, because a reader sees
"0 risks" and concludes the journey is clean when in fact nothing could ever have
been recorded.

The contract these tests pin, in order of how easy it is to get wrong:

1. The request body is strictly allow-listed. The browser never supplies
   organization_id or a created_by -- both come from the session, because a caller
   who can name the tenant can write into someone else's.
2. entity_type and relation are closed vocabularies. An unconstrained string lets a
   typo create an edge to a record type that does not exist, and nothing ever
   reports it: the link simply resolves to nothing and the reader sees a shorter
   list than the truth.
3. A duplicate is a duplicate, not a second fact.
4. A journey from another tenant is 404, never 403 -- distinguishing them would let
   a caller probe which journey ids exist elsewhere.
"""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture
def owner(db_session, make_org):
    from app.models.user import User

    org = make_org("journey-links")
    user = User(
        email=f"links-{uuid.uuid4().hex[:10]}@example.test",
        first_name="Lin",
        last_name="Ker",
        confirmed=True,
        organization_id=org.id,
        enterprise_role="enterprise_architect",
    )
    user.password = "test-password-not-secret"
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def journey(db_session, owner):
    from app.models.architecture_journey import ArchitectureJourney

    row = ArchitectureJourney(
        owner_id=owner.id,
        organization_id=owner.organization_id,
        title="Regulatory response",
        intent="risk_and_compliance",
        selected_layers=["motivation", "governance"],
    )
    db_session.add(row)
    db_session.flush()
    db_session.commit()
    return row


def _client(app, login_as, user):
    client = app.test_client()
    login_as(client, user)
    return client


def test_link_is_created_from_the_session_not_the_request(app, db_session, owner, journey, login_as):
    from app.models.architecture_journey_link import ArchitectureJourneyLink

    client = _client(app, login_as, owner)
    response = client.post(
        f"/architecture-journey/work/{journey.id}/links",
        json={"entity_type": "risk", "entity_id": 77, "relation": "impacts"},
    )
    assert response.status_code == 201, response.get_data(as_text=True)[:400]

    link = db_session.execute(
        db_session.query(ArchitectureJourneyLink)
        .filter_by(journey_id=journey.id)
        .statement
    ).scalar_one()
    assert link.entity_type == "risk"
    assert link.entity_id == 77
    assert link.relation == "impacts"
    # Never from the body.
    assert link.organization_id == owner.organization_id
    assert link.created_by_id == owner.id


def test_link_rejects_a_client_supplied_tenant_or_author(app, owner, journey, login_as):
    """A caller who can name the tenant can write into someone else's."""
    client = _client(app, login_as, owner)
    for forged in ("organization_id", "created_by_id"):
        response = client.post(
            f"/architecture-journey/work/{journey.id}/links",
            json={"entity_type": "risk", "entity_id": 1, forged: 999999},
        )
        assert response.status_code == 400, f"{forged} was accepted from the request body"


def test_link_rejects_an_unknown_entity_type_or_relation(app, owner, journey, login_as):
    client = _client(app, login_as, owner)

    bad_type = client.post(
        f"/architecture-journey/work/{journey.id}/links",
        json={"entity_type": "definitely_not_a_record", "entity_id": 1},
    )
    assert bad_type.status_code == 400

    bad_relation = client.post(
        f"/architecture-journey/work/{journey.id}/links",
        json={"entity_type": "risk", "entity_id": 1, "relation": "vibes"},
    )
    assert bad_relation.status_code == 400


def test_link_rejects_a_non_positive_entity_id(app, owner, journey, login_as):
    """A 0 or negative id points at no row and would render as a broken reference."""
    client = _client(app, login_as, owner)
    for value in (0, -3, "seven", None):
        response = client.post(
            f"/architecture-journey/work/{journey.id}/links",
            json={"entity_type": "decision", "entity_id": value},
        )
        assert response.status_code == 400, f"entity_id={value!r} was accepted"


def test_the_same_link_twice_is_a_conflict_not_a_second_fact(app, owner, journey, login_as):
    client = _client(app, login_as, owner)
    body = {"entity_type": "decision", "entity_id": 12, "relation": "produces"}

    assert client.post(f"/architecture-journey/work/{journey.id}/links", json=body).status_code == 201
    second = client.post(f"/architecture-journey/work/{journey.id}/links", json=body)
    assert second.status_code == 409


def test_link_can_be_removed_and_the_count_follows(app, db_session, owner, journey, login_as):
    from app.modules.solutions_strategic.v2.services.journey_home import journey_home_view

    client = _client(app, login_as, owner)
    created = client.post(
        f"/architecture-journey/work/{journey.id}/links",
        json={"entity_type": "risk", "entity_id": 5},
    )
    link_id = created.get_json()["data"]["id"]

    assert journey_home_view(journey_id=journey.id, actor_user=owner)["counts"]["risks"] == 1

    removed = client.delete(f"/architecture-journey/work/{journey.id}/links/{link_id}")
    assert removed.status_code == 200
    assert journey_home_view(journey_id=journey.id, actor_user=owner)["counts"]["risks"] == 0


def test_member_is_added_by_user_id_and_counted(app, db_session, owner, journey, login_as, make_org):
    from app.models.user import User
    from app.modules.solutions_strategic.v2.services.journey_home import journey_home_view

    colleague = User(
        email=f"colleague-{uuid.uuid4().hex[:10]}@example.test",
        confirmed=True,
        organization_id=owner.organization_id,
        enterprise_role="business_architect",
    )
    colleague.password = "test-password-not-secret"
    db_session.add(colleague)
    db_session.flush()
    db_session.commit()

    client = _client(app, login_as, owner)
    response = client.post(
        f"/architecture-journey/work/{journey.id}/members",
        json={"user_id": colleague.id, "role": "business_architect"},
    )
    assert response.status_code == 201, response.get_data(as_text=True)[:400]

    view = journey_home_view(journey_id=journey.id, actor_user=owner)
    assert view["counts"]["participants"] == 2  # the owner plus the colleague


def test_member_from_another_tenant_is_refused(app, db_session, owner, journey, login_as, make_org):
    """Adding a foreign user would put a name on a journey they cannot open."""
    from app.models.user import User

    other_org = make_org("journey-links-other")
    outsider = User(
        email=f"outsider-{uuid.uuid4().hex[:10]}@example.test",
        confirmed=True,
        organization_id=other_org.id,
        enterprise_role="solution_architect",
    )
    outsider.password = "test-password-not-secret"
    db_session.add(outsider)
    db_session.flush()
    db_session.commit()

    client = _client(app, login_as, owner)
    response = client.post(
        f"/architecture-journey/work/{journey.id}/members",
        json={"user_id": outsider.id, "role": "contributor"},
    )
    assert response.status_code == 400, "a user from another organisation was added"


def test_writes_to_another_tenants_journey_are_404(app, db_session, journey, login_as, make_org):
    """404 rather than 403: a 403 confirms the id exists."""
    from app.models.user import User

    other_org = make_org("journey-links-foreign")
    foreigner = User(
        email=f"foreign-{uuid.uuid4().hex[:10]}@example.test",
        confirmed=True,
        organization_id=other_org.id,
        enterprise_role="enterprise_architect",
    )
    foreigner.password = "test-password-not-secret"
    db_session.add(foreigner)
    db_session.flush()
    db_session.commit()

    client = _client(app, login_as, foreigner)
    response = client.post(
        f"/architecture-journey/work/{journey.id}/links",
        json={"entity_type": "risk", "entity_id": 1},
    )
    assert response.status_code == 404
