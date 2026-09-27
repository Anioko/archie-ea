"""C1: the capability-roadmap "Capability Gaps Detected" tile must count the same
population that "Detect Gaps" acts on and persists.

Before this fix, GET /capability-map/api/roadmap/gaps counted coverage gaps
across the SHARED technical-capability and APQC-process taxonomies (global
tables, not TenantMixin) with no capability_type filter applied by default,
while POST /capability-map/api/roadmap/gaps/detect only ever scans
BusinessCapability (a tenant-owned table). For a tenant with zero business
capabilities, this let the tile read a large tenant-independent number (the
shared taxonomy's own gap count) while Detect Gaps correctly reported
"0 created / 0 updated" and never moved the tile -- the exact defect reported
as C1.
"""

import pytest


@pytest.mark.usefixtures("db_session")
def test_gaps_tile_matches_detect_gaps_population_when_tenant_has_no_capabilities(
    app, db_session, make_org, tenant_ctx
):
    from app.models.user import User

    org = make_org("c1-gap-tile-reconciliation")
    with tenant_ctx(org.id):
        user = User(
            email=f"c1-gap-tile-{org.id}@example.com",
            organization_id=org.id,
            enterprise_role="enterprise_architect",
            confirmed=True,
        )
        db_session.add(user)
        db_session.commit()
        user_id = user.id

        from tests.test_ba_tenant_and_authz import _login

        c = app.test_client()
        with app.app_context():
            _login(c, user_id)

            # This tenant owns no BusinessCapability rows, so Detect Gaps -- which
            # only ever scans BusinessCapability -- must find nothing to do.
            detect_resp = c.post("/capability-map/api/roadmap/gaps/detect")
            assert detect_resp.status_code == 200, detect_resp.get_data(as_text=True)
            detect_body = detect_resp.get_json()
            assert detect_body["success"] is True
            assert detect_body["created"] == 0
            assert detect_body["updated"] == 0

            # The tile the page renders reads this same endpoint with no
            # capability_type query param. It must default to the same
            # (business-capability) population Detect Gaps operates on, not the
            # unfiltered shared technical/APQC taxonomy -- otherwise the tile can
            # show a large number that Detect Gaps can never reconcile to zero.
            gaps_resp = c.get("/capability-map/api/roadmap/gaps")
            assert gaps_resp.status_code == 200, gaps_resp.get_data(as_text=True)
            gaps_body = gaps_resp.get_json()
            assert gaps_body["gaps"] == []
