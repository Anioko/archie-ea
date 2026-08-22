"""Compatibility and browser intake contracts for programme setup."""

from __future__ import annotations

from app.models.solution_models import Solution
from app.modules.solutions_strategic.v2.services.programme_setup_service import ProgrammeSetupService

from tests.test_transformation_programme_service import _intake, _rows, programme_fixture


def test_compatibility_adapter_delegates_business_intake_without_solution(programme_fixture):
    """Catches the compatibility layer routing a business programme through legacy Solution creation."""
    result = ProgrammeSetupService.create_business_first_programme(
        actor=programme_fixture.actor,
        command_key="compatibility-intake",
        request=_intake(programme_fixture.owner_id),
    )
    rows = _rows(programme_fixture)
    assert result.object_ids["programme_id"] == rows["programme"].id
    assert rows["solutions"] == 0


def test_create_programme_route_rejects_forged_fields_and_returns_canonical_ids(
    app, programme_fixture, login_as
):
    """Catches browser intake trusting client identity/status or returning a Solution identifier."""
    client = app.test_client()
    login_as(client, programme_fixture.owner_id)
    payload = {
        "name": "Simplify the application estate",
        "objective": "Reduce duplicated capability cost without service loss",
        "owner_id": programme_fixture.owner_id,
        "target_date": "2027-06-30",
        "workstream_type": "application_rationalisation",
        "scope_expression": {"business_units": ["Retail"]},
        "outcome": _intake(programme_fixture.owner_id).outcome,
    }
    forged = client.post(
        "/solutions/create-programme",
        json={**payload, "organization_id": programme_fixture.foreign_organization_id, "status": "completed"},
        headers={"Idempotency-Key": "route-forged"},
    )
    assert forged.status_code == 400

    response = client.post(
        "/solutions/create-programme",
        json=payload,
        headers={"Idempotency-Key": "route-create"},
    )
    body = response.get_json()
    assert response.status_code == 201
    assert set(body) >= {
        "programme_id", "workstream_id", "outcome_commitment_id", "operation_result_id", "redirect_url"
    }
    assert "solution_id" not in body
    assert body["redirect_url"] == (
        f"/solutions/programmes/{body['programme_id']}/workstreams/{body['workstream_id']}/objective"
    )
    assert Solution.query.filter_by(organization_id=programme_fixture.organization_id).count() == 0


def test_new_programme_page_posts_canonical_business_payload_with_csrf_and_idempotency(
    app, programme_fixture, login_as
):
    """Catches the live wizard retaining its legacy Solution-only request/response contract."""
    client = app.test_client()
    login_as(client, programme_fixture.owner_id)
    response = client.get("/solutions/new-programme")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    for canonical_field in (
        "objective",
        "owner_id",
        "target_date",
        "target_date_unavailable_reason",
        "workstream_type",
        "scope_expression",
        "outcome",
        "metric_name",
        "aggregation",
    ):
        assert canonical_field in html
    assert "Idempotency-Key" in html
    assert "X-CSRFToken" in html
    assert "/api/users" in html
    assert "data.solution_id" not in html
    assert "mode: this.form.mode" not in html
    assert "window.location.href = data.redirect_url" in html
