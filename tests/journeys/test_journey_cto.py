"""Journey: can the cto persona set technology direction?

Level 9, docs/TESTING_STANDARD.md. The CTO's decision surface in Archie is the
technology radar: take a technology the enterprise has actually modelled and put
it in adopt / trial / assess / hold, with the reasoning attached. The journey is
classify -> persisted -> visible on the radar the organisation reads.

The radar deliberately refuses to invent entries: only a real Technology-layer
ArchiMateElement can be classified, so a hold ruling always points at something
that exists in the model. That refusal is asserted here too, because a radar
that accepts arbitrary ids is a radar that can show technology nobody runs.
"""

import uuid

import pytest

from .conftest import login, make_org, make_user

pytestmark = pytest.mark.journey


def _technology_element(db, org_id, name):
    from app.models.archimate_core import ArchiMateElement

    element = ArchiMateElement(
        name=name,
        type="Node",
        layer="Technology",
        organization_id=org_id,
        description="Modelled by the cto journey test.",
    )
    db.session.add(element)
    db.session.commit()
    return element.id


def test_cto_classifies_a_technology_and_the_radar_shows_it(app, client):
    """The persona's core write: a ring that persists and is visible."""
    from app import db
    from app.models.tech_radar import TechRadarEntry

    with app.app_context():
        org_id = make_org(db, "CTO")
        cto_id = make_user(db, org_id, "cto", enterprise_role="cto",
                           role_name="Architect")
        name = "Journey Runtime %s" % uuid.uuid4().hex[:8]
        element_id = _technology_element(db, org_id, name)

    login(client, cto_id)
    response = client.post(
        "/technology/radar/classify",
        data={
            "archimate_element_id": element_id,
            "ring": "hold",
            "rationale": "Superseded by the managed platform; no new adoption.",
        },
    )
    # The radar page submits a plain HTML form, so the persona's real path ends
    # on the radar -- not on a JSON body. This endpoint used to reply with
    # jsonify() unconditionally and navigate the CTO to a raw
    # {"success": true, ...} page with no way back.
    assert response.status_code == 302, response.data[:400]
    assert "/technology/radar" in response.headers["Location"]

    # PERSISTED
    with app.app_context():
        db.session.expunge_all()
        entry = db.session.execute(
            db.select(TechRadarEntry).filter_by(archimate_element_id=element_id)
        ).scalar_one()
        assert entry.ring == "hold"
        assert entry.set_by_user_id == cto_id
        # A ruling with no reasoning is a ruling nobody can challenge.
        assert entry.rationale == "Superseded by the managed platform; no new adoption."
        assert entry.organization_id == org_id

    # VISIBLE on the radar itself.
    page = client.get("/technology/radar/")
    assert page.status_code == 200, page.status_code
    assert name in page.get_data(as_text=True)


def test_the_radar_refuses_to_classify_something_that_is_not_modelled(app, client):
    """A radar entry can never be created out of thin air."""
    from app import db

    with app.app_context():
        org_id = make_org(db, "CTOGhost")
        cto_id = make_user(db, org_id, "ctoghost", enterprise_role="cto",
                           role_name="Architect")

    login(client, cto_id)
    response = client.post(
        "/technology/radar/classify",
        data={"archimate_element_id": 2147483000, "ring": "adopt", "rationale": "x"},
    )
    assert response.status_code == 400


def test_a_cto_cannot_classify_another_orgs_technology(app, client):
    """Technology direction is set per tenant."""
    from app import db
    from app.models.tech_radar import TechRadarEntry

    with app.app_context():
        org_a = make_org(db, "CTOOrgA")
        org_b = make_org(db, "CTOOrgB")
        cto_a = make_user(db, org_a, "ctoA", enterprise_role="cto",
                          role_name="Architect")
        element_id = _technology_element(
            db, org_b, "Foreign Runtime %s" % uuid.uuid4().hex[:8]
        )

    login(client, cto_a)
    response = client.post(
        "/technology/radar/classify",
        data={"archimate_element_id": element_id, "ring": "adopt", "rationale": "x"},
    )
    assert response.status_code == 400, response.status_code

    with app.app_context():
        db.session.expunge_all()
        assert db.session.execute(
            db.select(TechRadarEntry).filter_by(archimate_element_id=element_id)
        ).scalar_one_or_none() is None


def test_the_classify_api_still_answers_in_json(app, client):
    """The form path redirects; the API path must keep its JSON contract."""
    from app import db

    with app.app_context():
        org_id = make_org(db, "CTOApi")
        cto_id = make_user(db, org_id, "ctoapi", enterprise_role="cto",
                           role_name="Architect")
        element_id = _technology_element(db, org_id, "API Runtime %s" % uuid.uuid4().hex[:8])

    login(client, cto_id)
    response = client.post(
        "/technology/radar/classify",
        data={"archimate_element_id": element_id, "ring": "assess", "rationale": "Evaluating."},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert response.status_code == 200, response.data[:300]
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["entry"]["ring"] == "assess"
