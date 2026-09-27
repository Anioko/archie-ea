"""H1 (second half): risks mapped to an Application via the Risk Register's
"Map to…" picker must be visible on that application's own page -- the
finding's explicit "Show linked risks on those parent entities' detail
pages" requirement. Covers the Fact Sheet's new `linked_risks` context and
the manual-note disclaimer on the separate Risk posture fields.
"""

import pytest


@pytest.mark.usefixtures("db_session")
def test_build_fact_sheet_includes_linked_risks(app, db_session, make_org, tenant_ctx):
    from app.models.application_portfolio import ApplicationComponent
    from app.services import risk_service
    from app.services.application_fact_sheet import build_fact_sheet

    org = make_org("h1-factsheet")
    with tenant_ctx(org.id):
        component = ApplicationComponent(name="Payments Gateway", organization_id=org.id)
        db_session.add(component)
        db_session.flush()

        risk = risk_service.create_risk(
            solution_id=None, title="Single point of failure", description=None,
            likelihood=4, impact=4, owner="Platform team", mitigation_plan=None,
        )
        risk_service.add_risk_link(risk.id, "application", component.id)

        sheet = build_fact_sheet(component)
        assert "linked_risks" in sheet
        titles = [r["title"] for r in sheet["linked_risks"]]
        assert "Single point of failure" in titles


@pytest.mark.usefixtures("db_session")
def test_build_fact_sheet_linked_risks_empty_when_unmapped(app, db_session, make_org, tenant_ctx):
    from app.models.application_portfolio import ApplicationComponent
    from app.services.application_fact_sheet import build_fact_sheet

    org = make_org("h1-factsheet-empty")
    with tenant_ctx(org.id):
        component = ApplicationComponent(name="Unmapped App", organization_id=org.id)
        db_session.add(component)
        db_session.flush()

        sheet = build_fact_sheet(component)
        assert sheet["linked_risks"] == []


def test_fact_sheet_risk_posture_carries_manual_note():
    body = open("app/templates/applications/fact_sheet.html", encoding="utf-8").read()
    assert "Manually set" in body
    assert "not derived from the Risk Register" in body
