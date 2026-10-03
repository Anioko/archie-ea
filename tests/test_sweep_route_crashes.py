"""Regression tests for seven route crashes found by the tenant-isolation sweep.

Each route below handled a valid request from its own organisation without a
server error, so the isolation sweep can prove it refuses another organisation.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


@pytest.fixture
def org(make_org):
    return make_org("sweepcrash")


@pytest.fixture
def logged_in_client(app, db_session, org, login_as):
    from app.models.user import Permission, Role, User

    role = Role.query.filter_by(name="Administrator").first()
    if role is None:
        role = Role(name="Administrator", permissions=Permission.ADMINISTER)
        db_session.add(role)
        db_session.flush()

    user = User(
        email=f"sweepcrash-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Sweep",
        last_name="Crash",
        organization_id=org.id,
        role=role,
        confirmed=True,
    )
    db_session.add(user)
    db_session.flush()

    client = app.test_client()
    login_as(client, user)
    return client


# ── Fix 1: PATCH /api/adm-kanban/v2/deliverables/<id>/check ──────────────

def test_check_deliverable_succeeds_for_existing_deliverable(
    logged_in_client, db_session, org
):
    """A valid deliverable check must not 500 with a FK violation."""
    from app.models.adm_deliverable import ADMDeliverable

    d = ADMDeliverable(
        phase="A",
        name=f"Test deliverable {uuid.uuid4().hex[:8]}",
        description="Sweep test",
        is_template=True,
    )
    db_session.add(d)
    db_session.flush()

    resp = logged_in_client.patch(
        f"/api/adm-kanban/v2/deliverables/{d.id}/check",
        json={"board_id": 1, "checked": True},
    )
    assert resp.status_code == 200, (resp.status_code, resp.get_json())
    data = resp.get_json()
    assert data["success"] is True


def test_check_deliverable_returns_404_for_missing_deliverable(logged_in_client):
    """A non-existent deliverable must return 404, not 500 FK violation."""
    resp = logged_in_client.patch(
        "/api/adm-kanban/v2/deliverables/999999/check",
        json={"board_id": 1, "checked": True},
    )
    assert resp.status_code == 404, (resp.status_code, resp.get_json())


# ── Fix 2: POST /api/enterprise/requirements/<id>/generate-test-cases ────

def test_generate_test_cases_succeeds(logged_in_client, db_session, org):
    """Generating test cases must not fail with AttributeError on requirement_name."""
    from app.models.solution_architect_models import SolutionRequirement

    req = SolutionRequirement(
        name=f"Test req {uuid.uuid4().hex[:8]}",
        description="Sweep test requirement",
        acceptance_criteria="The system must respond within 200ms",
        organization_id=org.id,
    )
    db_session.add(req)
    db_session.flush()

    resp = logged_in_client.post(
        f"/api/enterprise/requirements/{req.id}/generate-test-cases",
    )
    assert resp.status_code == 200, (resp.status_code, resp.get_json())
    data = resp.get_json()
    assert "test_cases" in data


# ── Fix 3: POST /api/enterprise/solutions/<id>/populate-from-template ────

def test_populate_from_template_succeeds(logged_in_client, db_session, org):
    """Populating from template must not fail with AttributeError on is_active."""
    from app.models.requirement_template import RequirementTemplate
    from app.models.solution_architect_models import Solution

    sol = Solution(
        name=f"Test solution {uuid.uuid4().hex[:8]}",
        description="Sweep test",
        organization_id=org.id,
    )
    db_session.add(sol)
    db_session.flush()

    tpl = RequirementTemplate(
        name=f"Test template {uuid.uuid4().hex[:8]}",
        layer="business",
        is_system=True,
    )
    db_session.add(tpl)
    db_session.flush()

    resp = logged_in_client.post(
        f"/api/enterprise/solutions/{sol.id}/populate-from-template",
        json={"layers": ["business"]},
    )
    assert resp.status_code in (200, 201), (resp.status_code, resp.get_json())
    data = resp.get_json()
    assert data.get("solution_id") == sol.id


# ── Fix 4: POST /api/solutions/<id>/relationships/extract ────────────────

def test_extract_relationships_returns_clear_error(logged_in_client, db_session, org):
    """Missing orchestrator method must return a clear 400, not AttributeError."""
    from app.models.solution_architect_models import Solution

    sol = Solution(
        name=f"Test solution {uuid.uuid4().hex[:8]}",
        description="Sweep test",
        organization_id=org.id,
    )
    db_session.add(sol)
    db_session.flush()

    resp = logged_in_client.post(
        f"/api/solutions/{sol.id}/relationships/extract",
        json={"message": "The web frontend calls the order service"},
    )
    assert resp.status_code == 400, (resp.status_code, resp.get_json())
    data = resp.get_json()
    assert "error" in data


# ── Fix 5: POST /architecture/decisions/<id>/edit ────────────────────────

def test_edit_decision_without_title_does_not_500(logged_in_client, db_session, org):
    """Editing a decision without a title must keep the existing title, not 500."""
    from app.models.architecture_decision import ArchitectureDecision

    original_title = f"Original title {uuid.uuid4().hex[:8]}"
    decision = ArchitectureDecision(
        title=original_title,
        status="proposed",
        organization_id=org.id,
    )
    db_session.add(decision)
    db_session.flush()

    # POST without a title field — must not violate NOT NULL
    resp = logged_in_client.post(
        f"/architecture/decisions/{decision.id}/edit",
        data={"status": "accepted"},
        follow_redirects=True,
    )
    assert resp.status_code == 200, (resp.status_code, resp.get_json() if resp.is_json else "html")


# ── Fix 6: POST /dashboard/api/archimate-elements/<id>/correct ───────────

def test_archimate_element_correct_succeeds(logged_in_client, db_session, org):
    """Correcting an ArchiMate element must not fail with ModuleNotFoundError."""
    from app.models.archimate_core import ArchiMateElement

    elem = ArchiMateElement(
        name=f"Test element {uuid.uuid4().hex[:8]}",
        type="ApplicationComponent",
        layer="application",
        organization_id=org.id,
    )
    db_session.add(elem)
    db_session.flush()

    resp = logged_in_client.post(
        f"/dashboard/api/archimate-elements/{elem.id}/correct",
        json={"action": "approve"},
    )
    assert resp.status_code == 200, (resp.status_code, resp.get_json())
    data = resp.get_json()
    assert data["success"] is True


# ── Fix 7: POST /solutions/<id>/codegen/data/import ──────────────────────

def test_data_import_rejects_string_mappings(logged_in_client, db_session, org):
    """String mappings must be rejected with a clear 400, not AttributeError."""
    from app.models.solution_architect_models import Solution

    sol = Solution(
        name=f"Test solution {uuid.uuid4().hex[:8]}",
        description="Sweep test",
        organization_id=org.id,
    )
    db_session.add(sol)
    db_session.flush()

    resp = logged_in_client.post(
        f"/solutions/{sol.id}/codegen/data/import",
        json={
            "mappings": ["not_a_dict"],
            "rows": [{"col": "val"}],
        },
    )
    assert resp.status_code == 400, (resp.status_code, resp.get_json())
    data = resp.get_json()
    assert "mappings" in data.get("error", "").lower()