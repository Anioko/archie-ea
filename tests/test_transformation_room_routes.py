"""Stable, tenant-safe Transformation Room route contracts."""

from __future__ import annotations

from datetime import date

from app import db
from app.models.strategic import StrategicInitiative
from app.models.transformation_programme import ProgrammeWorkstream
from app.modules.transformation_room.programme_service import TransformationProgrammeService

from tests.test_transformation_programme_service import (
    _intake,
    programme_fixture,
    transformation_schema,
)


def _create_programme(scope, *, workstream_type="process"):
    return TransformationProgrammeService.create_programme(
        actor=scope.actor,
        command_key=f"room-route-{workstream_type}",
        request=_intake(
            scope.owner_id,
            workstream_type=workstream_type,
            target_date=date(2027, 6, 30),
        ),
    )


def test_canonical_root_redirects_to_overview_and_all_stable_urls_render(
    app, programme_fixture, login_as
):
    """Catches the create redirect landing on a missing page or transient-only tabs."""
    created = _create_programme(programme_fixture)
    programme_id = created.object_ids["programme_id"]
    workstream_id = created.object_ids["workstream_id"]
    client = app.test_client()
    login_as(client, programme_fixture.owner_id)

    root = client.get(f"/solutions/programmes/{programme_id}")
    assert root.status_code == 302
    assert root.headers["Location"].endswith(
        f"/solutions/programmes/{programme_id}/overview"
    )

    urls = [
        f"/solutions/programmes/{programme_id}/overview",
        f"/solutions/programmes/{programme_id}/workstreams",
        f"/solutions/programmes/{programme_id}/governance",
        f"/solutions/programmes/{programme_id}/roadmap",
        *[
            f"/solutions/programmes/{programme_id}/workstreams/{workstream_id}/{stage}"
            for stage in (
                "objective",
                "discover",
                "evidence",
                "options",
                "decision",
                "execute",
                "outcomes",
            )
        ],
    ]
    for url in urls:
        response = client.get(url)
        assert response.status_code == 200, url
        assert response.request.path == url


def test_room_loads_are_tenant_scoped_without_disclosing_foreign_ids(
    app, programme_fixture, login_as
):
    """Catches a globally valid programme/workstream ID leaking across organisations."""
    created = _create_programme(programme_fixture)
    programme_id = created.object_ids["programme_id"]
    workstream_id = created.object_ids["workstream_id"]
    client = app.test_client()
    login_as(client, programme_fixture.foreign_owner_id)

    assert client.get(f"/solutions/programmes/{programme_id}/overview").status_code == 404
    assert client.get(
        f"/solutions/programmes/{programme_id}/workstreams/{workstream_id}/objective"
    ).status_code == 404


def test_programme_list_includes_canonical_records_and_uses_room_link(
    app, programme_fixture, login_as
):
    """Catches canonical record_kind programmes disappearing from the legacy list query."""
    created = _create_programme(programme_fixture)
    programme_id = created.object_ids["programme_id"]
    client = app.test_client()
    login_as(client, programme_fixture.owner_id)

    response = client.get("/solutions/programmes")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Simplify the application estate" in body
    assert f'/solutions/programmes/{programme_id}/overview' in body
    assert "create-programme" not in body
    assert "Target platform" not in body
    assert "clean-core" not in body.lower()


def test_legacy_programme_root_remains_on_legacy_cockpit(
    app, programme_fixture, login_as
):
    """Catches the compatibility redirect treating old initiative rows as canonical."""
    with app.app_context():
        legacy = StrategicInitiative(
            organization_id=programme_fixture.organization_id,
            name="Legacy technology programme",
            description="Preserved compatibility record",
            initiative_type="brownfield",
            owner_id=programme_fixture.owner_id,
        )
        db.session.add(legacy)
        db.session.commit()
        legacy_id = legacy.id

    client = app.test_client()
    login_as(client, programme_fixture.owner_id)
    response = client.get(f"/solutions/programmes/{legacy_id}")

    assert response.status_code == 200
    assert response.request.path == f"/solutions/programmes/{legacy_id}"
    assert "Legacy technology programme" in response.get_data(as_text=True)


def test_objective_form_posts_through_public_service_and_redirects(
    app, programme_fixture, login_as
):
    """Catches a JavaScript-only objective edit or a route mutating the model directly."""
    created = _create_programme(programme_fixture)
    programme_id = created.object_ids["programme_id"]
    workstream_id = created.object_ids["workstream_id"]
    client = app.test_client()
    login_as(client, programme_fixture.owner_id)

    response = client.post(
        f"/solutions/programmes/{programme_id}/workstreams/{workstream_id}/objective",
        data={
            "objective": "Reduce customer hand-offs",
            "scope_expression": "Claims, Contact centre",
            "expected_revision": "1",
            "command_key": "objective-form-post",
        },
    )

    assert response.status_code == 303
    with app.app_context():
        workstream = db.session.get(ProgrammeWorkstream, workstream_id)
        assert workstream.objective == "Reduce customer hand-offs"
        assert workstream.scope_expression == {
            "business_units": ["Claims", "Contact centre"]
        }


def test_legacy_technology_first_programme_post_is_retired(
    app, programme_fixture, login_as
):
    client = app.test_client()
    login_as(client, programme_fixture.owner_id)

    response = client.post(
        "/solutions/programmes",
        json={"name": "Bypass", "initiative_type": "brownfield"},
    )

    assert response.status_code == 410
    assert response.get_json()["redirect_url"] == "/solutions/new-programme"
    with app.app_context():
        assert StrategicInitiative.query.filter_by(name="Bypass").first() is None
