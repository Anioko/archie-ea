"""Transformation Room information hierarchy and honest-state contracts."""

from __future__ import annotations

from app.modules.transformation_room.programme_service import TransformationProgrammeService

from tests.test_transformation_programme_service import (
    _intake,
    programme_fixture,
    transformation_schema,
)


def _room_page(app, scope, login_as, stage="objective", *, workstream_type="process"):
    created = TransformationProgrammeService.create_programme(
        actor=scope.actor,
        command_key=f"room-template-{stage}-{workstream_type}",
        request=_intake(scope.owner_id, workstream_type=workstream_type),
    )
    client = app.test_client()
    login_as(client, scope.owner_id)
    programme_id = created.object_ids["programme_id"]
    workstream_id = created.object_ids["workstream_id"]
    response = client.get(
        f"/solutions/programmes/{programme_id}/workstreams/{workstream_id}/{stage}"
    )
    return response, response.get_data(as_text=True), programme_id, workstream_id


def test_room_has_one_breadcrumb_and_complete_programme_header(
    app, programme_fixture, login_as
):
    """Catches duplicate hierarchy and omission of persisted programme context."""
    response, body, _programme_id, _workstream_id = _room_page(
        app, programme_fixture, login_as
    )

    assert response.status_code == 200
    assert body.count('aria-label="Breadcrumb"') == 1
    for label in (
        "Objective",
        "Lifecycle",
        "Owner",
        "Next action",
        "Evidence posture",
        "Expected outcome",
    ):
        assert label in body
    assert "Finance baseline requested" in body
    assert "—" in body


def test_stage_rail_is_directly_addressable_without_claiming_future_readiness(
    app, programme_fixture, login_as
):
    """Catches later-stage links being hidden or presented as active functionality."""
    for stage in ("decision", "execute", "outcomes"):
        response, body, programme_id, workstream_id = _room_page(
            app, programme_fixture, login_as, stage=stage
        )
        assert response.status_code == 200
        assert f"/solutions/programmes/{programme_id}/workstreams/{workstream_id}/{stage}" in body
        assert "Not available in this release" in body
        assert "Ready to advance" not in body


def test_non_technology_room_contains_no_solution_or_platform_claims(
    app, programme_fixture, login_as
):
    """Catches business transformation being framed as target-platform solution design."""
    _response, body, _programme_id, _workstream_id = _room_page(
        app, programme_fixture, login_as, workstream_type="process"
    )
    lowered = body.lower()
    assert "target platform" not in lowered
    assert "clean core" not in lowered
    assert "create technology solution" not in lowered


def test_owner_picker_is_an_accessible_keyboard_combobox(
    app, programme_fixture, login_as
):
    """Catches a mouse-only owner picker or stale hidden owner identity."""
    client = app.test_client()
    login_as(client, programme_fixture.owner_id)
    body = client.get("/solutions/new-programme").get_data(as_text=True)

    assert 'role="combobox"' in body
    assert 'aria-autocomplete="list"' in body
    assert '@keydown.arrow-down.prevent="moveOwner(1)"' in body
    assert '@keydown.arrow-up.prevent="moveOwner(-1)"' in body
    assert '@keydown.enter.prevent="chooseActiveOwner"' in body
    assert '@keydown.escape="closeOwnerPicker"' in body
    assert ':aria-activedescendant="activeOwnerId"' in body
    assert "this.form.owner_id = null" in body


def test_architect_synthesis_names_transformation_posture_without_relabelling_solutions(
    app, programme_fixture, login_as
):
    """Catches a Solution-only dashboard or a solution metric relabelled as enterprise truth."""
    TransformationProgrammeService.create_programme(
        actor=programme_fixture.actor,
        command_key="room-chief-rollup",
        request=_intake(programme_fixture.owner_id, workstream_type="process"),
    )
    client = app.test_client()
    login_as(client, programme_fixture.owner_id)
    response = client.get("/solutions/architect-synthesis")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    for label in (
        "Transformation posture",
        "Non-Solution programmes",
        "Evidence debt",
        "Decision ageing",
        "Cross-domain dependencies",
        "Delivery confidence",
        "Outcome variance",
        "Solution conformance",
    ):
        assert label in body
    assert "Not available in this release" in body
