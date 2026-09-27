"""D-R5-1: /api/roadmap/gaps/detect must read ONE store for both selection
and magnitude/prose, never a mix of the source (BusinessCapability) and the
authority (UnifiedCapability).

Before this fix, the selection predicate read the SOURCE
(`BusinessCapability.current_maturity_level`) while the magnitude and
persisted description read the AUTHORITY
(`UnifiedCapability.maturity_for_source`). Those two stores can disagree for
up to the 15-minute projection interval -- the raw-SQL UPDATE in
maturity_routes.py bypasses the ORM sync listener, and only the next
scheduled projection run catches the authority up. This let a capability be
SELECTED off a freshly-written source value while its magnitude/prose were
computed off a stale (still-NULL) authority row, persisting a Gap element
whose own description read "gap of 0" -- a Gap element asserting it has no
gap, contradicting its own existence.

This test plants exactly that divergence directly (a BusinessCapability with
a real maturity delta, but whose projected UnifiedCapability row is stale/
unprojected) and asserts the endpoint skips it entirely rather than
persisting a fabricated zero-gap Gap element.
"""

import pytest


@pytest.mark.usefixtures("db_session")
def test_detect_gaps_skips_capability_with_stale_unprojected_authority_row(
    app, db_session, make_org, tenant_ctx
):
    from app.models.business_capabilities import BusinessCapability
    from app.models.unified_capability import UnifiedCapability
    from app.models.user import User

    org = make_org("d-r5-1-divergence")
    with tenant_ctx(org.id):
        user = User(
            email=f"d-r5-1-{org.id}@example.com",
            organization_id=org.id,
            enterprise_role="enterprise_architect",
            confirmed=True,
        )
        db_session.add(user)
        db_session.commit()
        user_id = user.id

        # The SOURCE row has a real maturity delta (as if just written by
        # the raw-SQL UPDATE path in maturity_routes.py): current=4, target=5.
        cap = BusinessCapability(
            name="D-R5-1 divergent capability",
            code=f"CAP-DR51-{org.id}",
            organization_id=org.id,
            level=1,
            current_maturity_level=4,
            target_maturity_level=5,
        )
        db_session.add(cap)
        db_session.commit()

        # The write-time ORM sync listener already projected a
        # UnifiedCapability row for `cap` above. Force it back to the stale
        # (unprojected) state directly -- simulating the up-to-15-minute
        # window where the raw-SQL UPDATE in maturity_routes.py has landed
        # on the source but the scheduled projection run has not caught the
        # authority up yet.
        authority_row = UnifiedCapability.query.filter(
            UnifiedCapability.source_table == "business_capability",
            UnifiedCapability.source_id == str(cap.id),
        ).one()
        authority_row.current_maturity_level = None
        authority_row.target_maturity_level = None
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login

        c = app.test_client()
        _login(c, user_id)

        resp = c.post("/capability-map/api/roadmap/gaps/detect")
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["success"] is True

        # The divergent capability must be SKIPPED entirely -- no Gap
        # element created or updated for it while the authority is
        # stale, and in particular no persisted "gap of 0" fabrication.
        assert body["created"] == 0, (
            "a Gap element was created for a capability whose authority "
            "row is stale/unprojected -- this is the exact fabricated-"
            "zero-gap defect D-R5-1 fixes"
        )
        assert body["updated"] == 0
        gap_ids = [g["source_capability_id"] for g in body["gaps"]]
        assert cap.id not in gap_ids
