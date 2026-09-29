from __future__ import annotations

from datetime import datetime, timedelta


def _element(db_session, org_id: int, name: str):
    from app.models.archimate_core import ArchiMateElement

    row = ArchiMateElement(
        name=name,
        type="ApplicationComponent",
        layer="Application",
        organization_id=org_id,
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_same_external_id_is_scoped_per_organisation(db_session, make_org, tenant_ctx):
    from app.modules.intelligence.services.crosswalk_service import CrosswalkService

    org_a = make_org("crosswalk-a")
    org_b = make_org("crosswalk-b")

    with tenant_ctx(org_a.id):
        element_a = _element(db_session, org_a.id, "Order API")
        CrosswalkService.write_link("jira", "APP-123", element_a.id, confidence=0.91)

    with tenant_ctx(org_b.id):
        element_b = _element(db_session, org_b.id, "Finance API")
        CrosswalkService.write_link("jira", "APP-123", element_b.id, confidence=0.74)

    with tenant_ctx(org_a.id):
        link_a = CrosswalkService.get_link_by_external_id("jira", "APP-123")
        assert link_a is not None
        assert link_a.element_id == element_a.id
        assert CrosswalkService.get_links_for_element(element_b.id) == []

    with tenant_ctx(org_b.id):
        link_b = CrosswalkService.get_link_by_external_id("jira", "APP-123")
        assert link_b is not None
        assert link_b.element_id == element_b.id
        assert CrosswalkService.get_links_for_element(element_a.id) == []


def test_reimport_updates_existing_crosswalk_row_instead_of_creating_duplicate(
    db_session, make_org, tenant_ctx
):
    from app.models.external_identity_crosswalk import ExternalIdentityCrosswalk
    from app.modules.intelligence.services.crosswalk_service import CrosswalkService

    org = make_org("crosswalk-rename")
    original_seen = datetime.utcnow() - timedelta(days=2)
    renamed_seen = original_seen + timedelta(days=1)

    with tenant_ctx(org.id):
        original = _element(db_session, org.id, "Legacy Billing")
        renamed = _element(db_session, org.id, "Revenue Hub")

        first = CrosswalkService.write_link(
            "jira",
            "APP-456",
            original.id,
            confidence=0.52,
            first_seen=original_seen,
            last_seen=original_seen,
        )
        second = CrosswalkService.write_link(
            "jira",
            "APP-456",
            renamed.id,
            confidence=0.98,
            last_seen=renamed_seen,
        )

        rows = (
            db_session.query(ExternalIdentityCrosswalk)
            .filter_by(
                organization_id=org.id,
                source_system="jira",
                external_id="APP-456",
            )
            .all()
        )

        assert first.id == second.id
        assert len(rows) == 1
        assert rows[0].element_id == renamed.id
        assert rows[0].confidence == 0.98
        assert rows[0].first_seen == original_seen
        assert rows[0].last_seen == renamed_seen


def test_real_crosswalk_writer_is_clean_under_the_gate_scanner():
    from pathlib import Path

    from scripts.check_crosswalk_writer_gated import scan_file

    service_path = (
        Path(__file__).resolve().parents[4]
        / "app"
        / "modules"
        / "intelligence"
        / "services"
        / "crosswalk_service.py"
    )

    assert scan_file(str(service_path)) == []
