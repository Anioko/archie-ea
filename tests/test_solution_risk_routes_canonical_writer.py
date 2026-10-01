"""PR 316 ruling item 1: the solution risk tab's create/update/delete/CSV
import handlers must write through the canonical risk register
(app/services/risk_service.py) instead of creating a new ``solution_risks``
row -- the HIGH defect the review reproduced directly:

    POST /solutions/<id>/risks -> 201, solution_risks=1, canonical risks=0.

Request/response shapes are unchanged (SolutionRisk.to_dict()'s key set), and
the GET list on the same blueprint still reads solution_risks -- repointing
that reader is PR 2 scope, per the ruling.

Uses the shared fixtures in tests/conftest.py.
"""
import io
import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")

_RESPONSE_KEYS = {
    "id", "risk_name", "risk_description", "impact", "probability",
    "mitigation", "status", "owner", "retired_into_risk_id",
}


def _solution(db_session, org, name="Risk Route Solution"):
    from app.models.solution_models import Solution

    solution = Solution(name=f"{name} {uuid.uuid4().hex[:6]}", organization_id=org.id)
    db_session.add(solution)
    db_session.flush()
    return solution


def _user(db_session, org, label):
    from app.models.user import User

    user = User(email=f"{label}-{uuid.uuid4().hex[:8]}@example.com",
                first_name="Risk", last_name="Route",
                organization_id=org.id, confirmed=True)
    user.password = "not-used-in-tests-123"
    db_session.add(user)
    db_session.flush()
    return user


def test_create_route_writes_the_canonical_risk_and_leaves_the_old_table_unchanged(
        app, db_session, make_org, client, login_as):
    """The exact HIGH defect reproduction from the review, as an assertion."""
    from app.models.risk import Risk
    from app.models.risk_entity_link import RiskEntityLink
    from app.models.solution_lifecycle_models import SolutionRisk

    org = make_org("sol-risk-create")
    solution = _solution(db_session, org)
    user = _user(db_session, org, "sol-risk-creator")
    solution_id = solution.id

    # Scoped to this test's own solution: SolutionRisk.query.count() alone
    # would be a bare, tenant-unscoped count (g.current_org_id is not set
    # until the first authenticated request below), which also counts any
    # row belonging to a solution this test never touched.
    before_solution_risks = SolutionRisk.query.filter_by(solution_id=solution_id).count()

    login_as(client, user)
    resp = client.post(
        f"/solutions/{solution_id}/risks",
        json={
            "risk_name": "Route-created solution risk",
            "risk_description": "Still writes legacy table",
            "impact": "high",
            "probability": "medium",
            "mitigation": "Negotiate an exit clause.",
            "owner": "Platform team",
        },
    )
    assert resp.status_code == 201, resp.get_data(as_text=True)
    payload = resp.get_json()
    assert payload["success"] is True
    data = payload["data"]

    # Response shape matches the pre-existing SolutionRisk.to_dict() keys.
    assert set(data) == _RESPONSE_KEYS
    assert data["risk_name"] == "Route-created solution risk"
    assert data["risk_description"] == "Still writes legacy table"
    assert data["impact"] == "high"
    assert data["probability"] == "medium"
    assert data["mitigation"] == "Negotiate an exit clause."
    assert data["owner"] == "Platform team"
    assert data["status"] == "open"
    assert data["retired_into_risk_id"] is None

    # The canonical row exists ...
    risk = Risk.query.filter_by(id=data["id"]).first()
    assert risk is not None, "canonical risks row was never created"
    assert risk.solution_id == solution_id
    assert risk.title == "Route-created solution risk"
    assert risk.description == "Still writes legacy table"
    assert (risk.likelihood, risk.impact) == (3, 4)  # medium/high under _level_to_int
    link = RiskEntityLink.query.filter_by(risk_id=risk.id).one()
    assert (link.entity_type, link.entity_id) == ("solution", solution_id)

    # ... and the old table receives no new row.
    assert SolutionRisk.query.filter_by(solution_id=solution_id).count() == before_solution_risks


def test_create_route_never_lets_another_organisation_see_the_canonical_risk(
        app, db_session, make_org, client, login_as, tenant_ctx):
    """Two real organisations: organisation B can neither reach organisation
    A's solution through the route nor see the canonical row it created."""
    from app.models.risk import Risk

    org_a, org_b = make_org("sol-risk-a"), make_org("sol-risk-b")
    solution_a = _solution(db_session, org_a)
    user_a = _user(db_session, org_a, "sol-risk-org-a")
    user_b = _user(db_session, org_b, "sol-risk-org-b")
    solution_a_id = solution_a.id

    login_as(client, user_a)
    resp = client.post(
        f"/solutions/{solution_a_id}/risks",
        json={"risk_name": "Org A risk", "risk_description": "Org A only",
              "impact": "high", "probability": "medium"},
    )
    assert resp.status_code == 201, resp.get_data(as_text=True)
    risk_id = resp.get_json()["data"]["id"]

    # Organisation B cannot even address organisation A's solution.
    login_as(client, user_b)
    resp_b = client.post(
        f"/solutions/{solution_a_id}/risks",
        json={"risk_name": "Should not be reachable", "risk_description": "x",
              "impact": "low", "probability": "low"},
    )
    assert resp_b.status_code == 404

    # Organisation B cannot see the canonical row either, at the ORM level.
    with tenant_ctx(org_b.id):
        assert Risk.query.filter_by(id=risk_id).first() is None


def test_update_route_writes_through_the_canonical_risk(
        app, db_session, make_org, client, login_as):
    from app.models.risk import Risk
    from app.models.solution_lifecycle_models import SolutionRisk

    org = make_org("sol-risk-update")
    solution = _solution(db_session, org)
    user = _user(db_session, org, "sol-risk-updater")
    solution_id = solution.id

    login_as(client, user)
    created = client.post(
        f"/solutions/{solution_id}/risks",
        json={"risk_name": "Initial name", "risk_description": "Initial text",
              "impact": "low", "probability": "low"},
    ).get_json()["data"]
    risk_id = created["id"]
    before_solution_risks = SolutionRisk.query.filter_by(solution_id=solution_id).count()

    resp = client.put(
        f"/solutions/{solution_id}/risks/{risk_id}",
        json={"risk_description": "Updated by the route", "impact": "critical",
              "status": "mitigated"},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert set(data) == _RESPONSE_KEYS
    assert data["risk_description"] == "Updated by the route"
    assert data["impact"] == "critical"
    assert data["status"] == "mitigated"
    # A field not sent is echoed back unchanged, not blanked.
    assert data["risk_name"] == "Initial name"

    risk = Risk.query.filter_by(id=risk_id).one()
    assert risk.description == "Updated by the route"
    assert risk.impact == 5  # "critical" under _level_to_int
    assert risk.status.value == "mitigated"

    # No row was ever added to the superseded store.
    assert SolutionRisk.query.filter_by(solution_id=solution_id).count() == before_solution_risks == 0


def test_delete_route_removes_the_canonical_risk_without_ever_creating_a_solution_risk_row(
        app, db_session, make_org, client, login_as):
    from app.models.risk import Risk
    from app.models.solution_lifecycle_models import SolutionRisk

    org = make_org("sol-risk-delete")
    solution = _solution(db_session, org)
    user = _user(db_session, org, "sol-risk-deleter")
    solution_id = solution.id

    login_as(client, user)
    created = client.post(
        f"/solutions/{solution_id}/risks",
        json={"risk_name": "To be deleted", "risk_description": "x",
              "impact": "medium", "probability": "medium"},
    ).get_json()["data"]
    risk_id = created["id"]
    assert SolutionRisk.query.filter_by(solution_id=solution_id).count() == 0

    resp = client.delete(f"/solutions/{solution_id}/risks/{risk_id}")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()["success"] is True

    assert Risk.query.filter_by(id=risk_id).first() is None
    assert SolutionRisk.query.filter_by(solution_id=solution_id).count() == 0


def test_csv_import_writes_through_the_canonical_risk_and_leaves_the_old_table_unchanged(
        app, db_session, make_org, client, login_as):
    from app.models.risk import Risk
    from app.models.risk_entity_link import RiskEntityLink
    from app.models.solution_lifecycle_models import SolutionRisk

    org = make_org("sol-risk-import")
    solution = _solution(db_session, org)
    user = _user(db_session, org, "sol-risk-importer")
    solution_id = solution.id

    csv_text = (
        "description,name,impact,probability,mitigation,status,owner\n"
        "No viable exit path,Vendor lock-in,high,medium,Escrow clause,open,Jamie\n"
        "Single point of failure,Key-person risk,critical,high,Cross-train staff,open,Jamie\n"
    )

    login_as(client, user)
    resp = client.post(
        f"/solutions/{solution_id}/risks/import",
        data={"file": (io.BytesIO(csv_text.encode("utf-8")), "risks.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    payload = resp.get_json()
    assert payload["success"] is True
    assert payload["created"] == 2
    assert payload["errors"] == []

    risks = Risk.query.filter_by(solution_id=solution_id).order_by(Risk.id).all()
    assert [r.title for r in risks] == ["Vendor lock-in", "Key-person risk"]
    for risk in risks:
        link = RiskEntityLink.query.filter_by(risk_id=risk.id).one()
        assert (link.entity_type, link.entity_id) == ("solution", solution_id)

    # The old table receives no new rows from the import either.
    assert SolutionRisk.query.filter_by(solution_id=solution_id).count() == 0
