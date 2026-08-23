"""Compatibility and browser intake contracts for programme setup."""

from __future__ import annotations

import re

from app.models.solution_models import Solution
from app.models.transformation_programme import WORKSTREAM_TYPES
from app.modules.solutions_strategic.v2.services.programme_setup_service import ProgrammeSetupService

from tests.test_transformation_programme_service import _intake, _rows, programme_fixture


def _hidden_value(html: str, name: str) -> str:
    match = re.search(
        rf'<input[^>]*name="{re.escape(name)}"[^>]*value="([^"]*)"', html
    )
    assert match is not None
    return match.group(1)


def _form_payload(owner_id: int, **changes):
    request = _intake(owner_id)
    values = {
        "name": request.name,
        "objective": request.objective,
        "owner_id": str(request.owner_id),
        "target_date": request.target_date.isoformat(),
        "target_date_unavailable_reason": "",
        "workstream_type": request.workstream_type,
        "scope_expression": "Retail",
        "outcome": request.outcome["statement"],
        "direction": request.outcome["direction"],
        "metric_name": request.outcome["measure"]["metric_name"],
        "unit": request.outcome["measure"]["unit"],
        "currency": request.outcome["measure"]["currency"],
        "aggregation": request.outcome["measure"]["aggregation"],
        "baseline_value": "",
        "unavailable_reason": request.outcome["measure"]["unavailable_reason"],
        "target_value": request.outcome["measure"]["target_value"],
    }
    values.update(changes)
    return values


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
    assert re.search(
        r'<form[^>]*method="post"[^>]*action="/solutions/create-programme"',
        html,
    )
    assert _hidden_value(html, "csrf_token")
    assert _hidden_value(html, "command_key")

    workstream_select = re.search(
        r'<select[^>]*name="workstream_type".*?</select>', html, re.DOTALL
    )
    assert workstream_select is not None
    rendered_types = tuple(
        re.findall(r'<option value="([a-z_]+)"[^>]*>', workstream_select.group())
    )
    assert rendered_types == WORKSTREAM_TYPES


def test_create_programme_route_accepts_every_canonical_workstream_type(
    app, programme_fixture, login_as
):
    """Catches a rendered workstream choice that canonical validation rejects."""
    client = app.test_client()
    login_as(client, programme_fixture.owner_id)
    for index, workstream_type in enumerate(WORKSTREAM_TYPES):
        request = _intake(programme_fixture.owner_id)
        payload = {
            "name": f"Canonical workstream {index}",
            "objective": request.objective,
            "owner_id": request.owner_id,
            "target_date": request.target_date.isoformat(),
            "workstream_type": workstream_type,
            "scope_expression": request.scope_expression,
            "outcome": request.outcome,
        }
        response = client.post(
            "/solutions/create-programme",
            json=payload,
            headers={"Idempotency-Key": f"canonical-workstream-{workstream_type}"},
        )
        assert response.status_code == 201, (workstream_type, response.get_json())
        assert "solution_id" not in response.get_json()


def test_no_javascript_form_post_creates_and_redirects_to_objective(
    app, programme_fixture, login_as
):
    client = app.test_client()
    login_as(client, programme_fixture.owner_id)
    page = client.get("/solutions/new-programme")
    html = page.get_data(as_text=True)
    form = _form_payload(programme_fixture.owner_id)
    form.update(
        csrf_token=_hidden_value(html, "csrf_token"),
        command_key=_hidden_value(html, "command_key"),
    )

    response = client.post("/solutions/create-programme", data=form)

    assert response.status_code == 303
    assert re.fullmatch(
        r"/solutions/programmes/\d+/workstreams/\d+/objective",
        response.headers["Location"],
    )
    rows = _rows(programme_fixture)
    assert rows["programme"].name == form["name"]
    assert rows["workstreams"][0].scope_expression == {
        "business_units": ["Retail"]
    }
    assert rows["solutions"] == 0


def test_no_javascript_validation_rerenders_honest_input_and_errors(
    app, programme_fixture, login_as
):
    client = app.test_client()
    login_as(client, programme_fixture.owner_id)
    page = client.get("/solutions/new-programme")
    html = page.get_data(as_text=True)
    form = _form_payload(
        programme_fixture.owner_id,
        name="   ",
        objective="Keep this honestly entered objective",
    )
    form.update(
        csrf_token=_hidden_value(html, "csrf_token"),
        command_key=_hidden_value(html, "command_key"),
    )

    response = client.post("/solutions/create-programme", data=form)
    body = response.get_data(as_text=True)

    assert response.status_code == 400
    assert "name is required" in body
    assert "Keep this honestly entered objective" in body
    assert _hidden_value(body, "command_key") == form["command_key"]
    assert _rows(programme_fixture)["programme"] is None


def test_form_post_uses_login_csrf_and_tenant_authorisation_conventions(
    app, programme_fixture, login_as
):
    anonymous = app.test_client()
    assert anonymous.post(
        "/solutions/create-programme",
        data=_form_payload(programme_fixture.owner_id, command_key="anonymous"),
    ).status_code in {302, 401}

    client = app.test_client()
    login_as(client, programme_fixture.owner_id)
    page = client.get("/solutions/new-programme")
    html = page.get_data(as_text=True)
    form = _form_payload(
        programme_fixture.foreign_owner_id,
        command_key=_hidden_value(html, "command_key"),
        csrf_token=_hidden_value(html, "csrf_token"),
    )
    response = client.post("/solutions/create-programme", data=form)

    assert response.status_code == 404
    assert "owner_not_found" in response.get_data(as_text=True)
    assert _rows(programme_fixture)["programme"] is None
