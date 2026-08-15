"""Behavioural coverage of the Solutions v2 write paths (solution_design_bp).

Exercises the core lifecycle through the real HTTP layer (Flask test client),
against the shared fixtures in tests/conftest.py:

  create (POST /solutions/create-with-draft)
    -> GET detail
    -> update ordinary fields (PUT /solutions/<id>/update-json)
    -> GET again, assert persisted
    -> bad input on the same endpoints: never a 500
    -> architecture decisions sub-resource (POST/PUT/approve/reject)
    -> cross-tenant isolation

`create-with-draft` calls into `SolutionAIOrchestrator` (an LLM-backed service)
to generate a draft architecture, but the call is wrapped in a bare
try/except in the route itself (solution_design_routes.py) that only logs a
warning on failure — so with no LLM provider configured in the test
environment (confirmed by the "No LLM provider configured" boot warning) the
endpoint still returns 200 and creates the Solution row; no mocking is
required to exercise the write path itself. No test here asserts on any
LLM-generated content.

Defect found + fixed in solution_design_routes.py `api_update_solution`
(PUT /solutions/<id>/update-json):
  1. Fields advertised as editable via `_EDITABLE_FIELDS` (used for the
     "unknown fields" 422 check) — estimated_cost, roi_percentage, the three
     date fields, solution_type, complexity_level, business_value,
     scope_description/in/out, affected_systems — were silently accepted
     but never assigned to the model. A client submitting `estimated_cost`
     got back `{"success": true}` and the value was silently dropped. Fixed
     by actually applying every field in `_EDITABLE_FIELDS`.
  2. An oversized `name` (or any bounded string field) reached the DB
     unchecked, so Postgres raised a DataError at commit that the generic
     `except Exception` turned into an opaque 500. Fixed with an explicit
     length check returning 400.
  3. A non-numeric `estimated_cost` / non-ISO `planned_start_date` hit the
     same silent-drop bug (1) rather than erroring, so the 500 was masked
     by the no-op; fixing (1) surfaced it as an uncaught cast failure caught
     by the outer `except Exception` -> 500. Fixed by validating/parsing
     each field up front and returning 400 with a field-specific message on
     failure, before any attribute is set on the model.
"""

from __future__ import annotations

import uuid

import pytest


def _clear_g_cache():
    """Drop cached flask_login/tenant state from Flask's ``g``.

    The shared `db_session` fixture keeps every request in a test inside one
    outer app context — Flask reuses it instead of pushing a fresh one per
    test-client call — so `g._login_user` (and the tenant middleware's
    `g.current_org_id`) from a *previous* request survive into the next one
    unless cleared. A real HTTP request never has this problem (each gets a
    fresh app context and thus a fresh `g`); it only bites tests that make
    several requests, as different users, inside one `db_session`. See
    tests/test_ba_tenant_and_authz.py::_login for the same root cause.
    Call this before every request that follows a *different* client's
    request, not just at login time.
    """
    from flask import g, has_app_context

    if not has_app_context():
        return
    for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
        if hasattr(g, cached):
            delattr(g, cached)


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
    _clear_g_cache()


@pytest.fixture
def solution_setup(app, db_session, make_org):
    from app.models.user import User

    org = make_org("sol")
    user = User(
        email=f"sol-owner-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Sol",
        last_name="Owner",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="platform_admin",
    )
    db_session.add(user)
    db_session.flush()

    client = app.test_client()
    _login(client, user.id)
    return client, org, user


def _create_solution(client, title="QA Wave Solution", brief="A test solution brief."):
    resp = client.post(
        "/solutions/create-with-draft",
        json={"title": title, "brief": brief},
    )
    return resp


def test_create_solution(solution_setup):
    """POST create-with-draft returns success and persists a Solution row."""
    client, org, user = solution_setup
    from app.models.solution_models import Solution

    resp = _create_solution(client, title="QA Wave Solution Alpha")
    assert resp.status_code in (200, 201, 302), resp.get_data(as_text=True)

    body = resp.get_json(silent=True)
    assert body and body.get("solution_id"), body
    solution_id = body["solution_id"]

    solution = Solution.query.get(solution_id)
    assert solution is not None
    assert solution.name == "QA Wave Solution Alpha"
    assert solution.organization_id == org.id
    assert solution.created_by_id == user.id


def test_detail_page_renders_and_shows_name(solution_setup):
    client, org, user = solution_setup
    resp = _create_solution(client, title="QA Wave Detail Target")
    solution_id = resp.get_json()["solution_id"]

    resp = client.get(f"/solutions/{solution_id}")
    assert resp.status_code == 200
    assert "QA Wave Detail Target" in resp.get_data(as_text=True)


def test_update_ordinary_fields_persist(solution_setup):
    client, org, user = solution_setup
    from app.models.solution_models import Solution

    solution_id = _create_solution(client, title="QA Wave Update Target").get_json()["solution_id"]

    resp = client.put(
        f"/solutions/{solution_id}/update-json",
        json={
            "name": "QA Wave Updated Name",
            "description": "Updated description text.",
            "business_domain": "Finance",
        },
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()["success"] is True

    # Re-GET via a fresh query — not the request's own identity-map object —
    # to actually prove persistence rather than an in-memory mutation.
    solution = Solution.query.get(solution_id)
    assert solution.name == "QA Wave Updated Name"
    assert solution.description == "Updated description text."
    assert solution.business_domain == "Finance"

    resp = client.get(f"/solutions/{solution_id}")
    assert resp.status_code == 200
    assert "QA Wave Updated Name" in resp.get_data(as_text=True)


def test_update_decimal_and_date_fields_persist(solution_setup):
    """Regression test for defect (1): these fields were silently dropped."""
    client, org, user = solution_setup
    from app.models.solution_models import Solution
    from decimal import Decimal
    from datetime import date

    solution_id = _create_solution(client, title="QA Wave Numeric Target").get_json()["solution_id"]

    resp = client.put(
        f"/solutions/{solution_id}/update-json",
        json={"estimated_cost": 12345.67, "roi_percentage": 42.5, "planned_start_date": "2026-01-15"},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)

    solution = Solution.query.get(solution_id)
    assert solution.estimated_cost == Decimal("12345.67")
    assert solution.roi_percentage == 42.5
    assert solution.planned_start_date == date(2026, 1, 15)


class TestBadInputNeverCrashes:
    """Every write endpoint touched above, fed malformed input: 4xx, never 5xx."""

    def test_update_unknown_field_is_422(self, solution_setup):
        client, org, user = solution_setup
        solution_id = _create_solution(client).get_json()["solution_id"]

        resp = client.put(f"/solutions/{solution_id}/update-json", json={"bogus_field": "x"})
        assert resp.status_code == 422
        assert resp.get_json()["success"] is False

    def test_update_non_numeric_cost_is_400_not_500(self, solution_setup):
        client, org, user = solution_setup
        solution_id = _create_solution(client).get_json()["solution_id"]

        resp = client.put(f"/solutions/{solution_id}/update-json", json={"estimated_cost": "not-a-number"})
        assert resp.status_code == 400, resp.get_data(as_text=True)
        assert "estimated_cost" in resp.get_json()["error"]

    def test_update_bad_date_is_400_not_500(self, solution_setup):
        client, org, user = solution_setup
        solution_id = _create_solution(client).get_json()["solution_id"]

        resp = client.put(f"/solutions/{solution_id}/update-json", json={"planned_start_date": "not-a-date"})
        assert resp.status_code == 400, resp.get_data(as_text=True)
        assert "planned_start_date" in resp.get_json()["error"]

    def test_update_oversized_name_is_400_not_500(self, solution_setup):
        client, org, user = solution_setup
        solution_id = _create_solution(client).get_json()["solution_id"]

        resp = client.put(f"/solutions/{solution_id}/update-json", json={"name": "x" * 5000})
        assert resp.status_code == 400, resp.get_data(as_text=True)
        assert "name" in resp.get_json()["error"]

    def test_update_empty_name_is_400_not_500(self, solution_setup):
        client, org, user = solution_setup
        solution_id = _create_solution(client).get_json()["solution_id"]

        resp = client.put(f"/solutions/{solution_id}/update-json", json={"name": ""})
        assert resp.status_code == 400

    def test_get_nonexistent_solution_is_404(self, solution_setup):
        client, org, user = solution_setup
        resp = client.get("/solutions/999999999")
        assert resp.status_code == 404

    def test_update_nonexistent_solution_is_404(self, solution_setup):
        client, org, user = solution_setup
        resp = client.put("/solutions/999999999/update-json", json={"name": "x"})
        assert resp.status_code == 404

    def test_create_decision_missing_title_is_400(self, solution_setup):
        client, org, user = solution_setup
        solution_id = _create_solution(client).get_json()["solution_id"]

        resp = client.post(f"/solutions/{solution_id}/decisions", json={})
        assert resp.status_code == 400
        assert resp.get_json()["success"] is False

    def test_create_decision_invalid_type_is_400(self, solution_setup):
        client, org, user = solution_setup
        solution_id = _create_solution(client).get_json()["solution_id"]

        resp = client.post(
            f"/solutions/{solution_id}/decisions",
            json={"title": "Use Postgres", "decision_type": "not-a-real-type"},
        )
        assert resp.status_code == 400

    def test_update_nonexistent_decision_is_404(self, solution_setup):
        client, org, user = solution_setup
        solution_id = _create_solution(client).get_json()["solution_id"]

        resp = client.put(f"/solutions/{solution_id}/decisions/999999", json={"title": "x"})
        assert resp.status_code == 404

    def test_reject_decision_without_reason_is_400(self, solution_setup):
        client, org, user = solution_setup
        solution_id = _create_solution(client).get_json()["solution_id"]

        resp = client.post(f"/solutions/{solution_id}/decisions", json={"title": "Use Postgres"})
        assert resp.status_code == 201
        decision_id = resp.get_json()["data"]["id"]

        resp = client.post(f"/solutions/{solution_id}/decisions/{decision_id}/reject", json={})
        assert resp.status_code == 400


def test_decision_lifecycle_create_update_approve(solution_setup):
    client, org, user = solution_setup
    solution_id = _create_solution(client).get_json()["solution_id"]

    resp = client.post(
        f"/solutions/{solution_id}/decisions",
        json={"title": "Use managed Postgres", "decision_type": "vendor_selection"},
    )
    assert resp.status_code == 201, resp.get_data(as_text=True)
    decision = resp.get_json()["data"]
    assert decision["title"] == "Use managed Postgres"
    decision_id = decision["id"]

    resp = client.put(
        f"/solutions/{solution_id}/decisions/{decision_id}",
        json={"rationale": "Reduces ops burden."},
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["rationale"] == "Reduces ops burden."

    resp = client.post(f"/solutions/{solution_id}/decisions/{decision_id}/approve")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["status"] == "approved"

    # An already-approved decision can no longer be edited.
    resp = client.put(f"/solutions/{solution_id}/decisions/{decision_id}", json={"title": "New title"})
    assert resp.status_code == 409


def test_cross_tenant_cannot_read_or_write_others_solution(app, db_session, make_org):
    """Org B must not be able to GET or update Org A's solution: 404, never 200/500."""
    from app.models.user import User

    org_a = make_org("cross-a")
    user_a = User(
        email=f"cross-a-{uuid.uuid4().hex[:8]}@example.com",
        first_name="A",
        last_name="Owner",
        organization_id=org_a.id,
        confirmed=True,
        enterprise_role="platform_admin",
    )
    db_session.add(user_a)
    db_session.flush()

    client_a = app.test_client()
    _login(client_a, user_a.id)
    solution_id = _create_solution(client_a, title="Org A Confidential Solution").get_json()["solution_id"]

    # The shared db_session fixture keeps this whole test inside one app
    # context (see _login's docstring note), so the Solution row just loaded
    # by org A sits in the session's identity map. `.get()`/`get_or_404()`
    # only re-applies the tenant filter on a *miss* (see CLAUDE.md's
    # tenant-isolation note and tests/test_tenant_isolation.py) — a real HTTP
    # request always gets a fresh session, but this in-process test does not
    # unless told to. Clear it so the next request's `.get()` genuinely hits
    # the DB and the tenant filter has something to enforce.
    db_session.expunge_all()

    org_b = make_org("cross-b")
    user_b = User(
        email=f"cross-b-{uuid.uuid4().hex[:8]}@example.com",
        first_name="B",
        last_name="Intruder",
        organization_id=org_b.id,
        confirmed=True,
        enterprise_role="platform_admin",
    )
    db_session.add(user_b)
    db_session.flush()

    client_b = app.test_client()
    _login(client_b, user_b.id)

    resp = client_b.get(f"/solutions/{solution_id}")
    assert resp.status_code == 404, resp.get_data(as_text=True)

    resp = client_b.put(f"/solutions/{solution_id}/update-json", json={"name": "hacked"})
    assert resp.status_code == 404, resp.get_data(as_text=True)

    # Confirm the write was actually rejected (not applied then hidden) by
    # reading it back as org A — the only session with the right tenant
    # context set on `g` right now (see the identity-map note above; the
    # same reasoning applies to querying directly here, so go back through
    # org A's own client instead of touching Solution.query directly).
    db_session.expunge_all()
    _clear_g_cache()
    resp = client_a.get(f"/solutions/{solution_id}")
    assert resp.status_code == 200
    assert "Org A Confidential Solution" in resp.get_data(as_text=True)
    assert "hacked" not in resp.get_data(as_text=True)
