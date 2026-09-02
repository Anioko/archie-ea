"""F-15/F-16, Capgemini walkthrough:
- F-15 (decision lens): the Enterprise Posture "Architecture decisions" tile
  counted app.models.adr.ArchitectureDecisionRecord, a store nothing links to
  (architecture_decision_records, orphaned). The real ADR list
  (arch_decisions.list_decisions) is backed by
  app.models.architecture_decision.ArchitectureDecision over
  architecture_decisions. Assert the lens now counts the real table.
- F-16: /organization/chart/api/data and /organization/raci/api/data wrap
  their payload in success_response() -> {"data": {...}}; assert the shape,
  since the JS bug was in reading it, not in the route.
"""

import pytest


@pytest.mark.usefixtures("db_session")
def test_decision_lens_counts_the_real_adr_table(app, db_session, make_org, tenant_ctx):
    from app.models.architecture_decision import ArchitectureDecision
    from app.modules.solutions_strategic.v2.services.enterprise_posture_service import (
        EnterprisePostureService,
    )

    org = make_org("posture-decision-lens")
    with tenant_ctx(org.id):
        db_session.add(ArchitectureDecision(
            title="Adopt canonical capability store",
            status="accepted",
            rationale="ADR-0008",
            consequences="single source of truth",
            organization_id=org.id,
        ))
        db_session.commit()

        with app.app_context():
            lens, _attention = EnterprisePostureService._decision_lens()
            assert lens["total"] >= 1
            assert lens["state"] == "measured"


@pytest.mark.usefixtures("db_session")
def test_org_chart_and_raci_apis_are_envelope_wrapped(app, db_session, make_org, tenant_ctx):
    from app.models.user import User

    org = make_org("org-chart-raci-envelope")
    with tenant_ctx(org.id):
        user = User(email=f"ocr-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)

            chart_resp = c.get("/organization/chart/api/data")
            assert chart_resp.status_code == 200
            chart_body = chart_resp.get_json()
            assert "data" in chart_body
            assert "actor_count" in chart_body["data"] or "groups" in chart_body["data"]

            raci_resp = c.get("/organization/raci/api/data")
            assert raci_resp.status_code == 200
            raci_body = raci_resp.get_json()
            assert "data" in raci_body
            assert "capabilities" in raci_body["data"]
